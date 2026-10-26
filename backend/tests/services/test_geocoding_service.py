from models import Category, CategoryType
from services import GeocodingService
from wikipedia import Article


class FakeWikipedia:
    def __init__(self, titles: dict[str, Article | None]):
        self.titles = titles
        self.looked_up = []

    def lookup(self, titles):
        titles = list(titles)
        self.looked_up.append(titles)
        return {title: self.titles.get(title) for title in titles}


def article(title: str, **kwargs) -> Article:
    url = "https://ca.wikipedia.org/wiki/" + title.replace(" ", "_")
    return Article(title=title, url=url, **kwargs)


def location(name: str, **kwargs) -> Category:
    return Category(
        name=name,
        slug=Category.slugify_name(name),
        type=CategoryType.LOCATION,
        **kwargs,
    )


class TestGeocodingService:
    def test_places_locations_at_their_articles_coordinates(self):
        wikipedia = FakeWikipedia(
            {
                "Montserrat": article("Montserrat", coordinates=(41.6, 1.8)),
                "Washington": article(
                    "Washington", disambiguation=True, coordinates=(1, 2)
                ),
                "Via Laietana": article("Via Laietana"),
            }
        )
        montserrat = location("Montserrat")
        washington = location("Washington")
        laietana = location("Via Laietana")
        diodati = location("Villa Diodati")

        unplaced = GeocodingService(wikipedia).geocode(
            [montserrat, washington, laietana, diodati]
        )

        assert (montserrat.latitude, montserrat.longitude) == (41.6, 1.8)
        assert unplaced == [washington, laietana, diodati]
        for place in unplaced:
            assert place.latitude is None and place.longitude is None
        # All looked up, in one go: a place that can't be found stays off
        # the map until the admin places it.
        assert wikipedia.looked_up == [
            ["Montserrat", "Washington", "Via Laietana", "Villa Diodati"]
        ]
        for place in (montserrat, *unplaced):
            assert place.geocoded_at

    def test_keeps_the_coordinates_of_a_location_it_cant_place(self):
        # A location renamed in the admin, to a name with no article.
        raval = location("Barri Xino", latitude=41.38, longitude=2.17)

        unplaced = GeocodingService(FakeWikipedia({})).geocode([raval])

        assert unplaced == [raval]
        assert (raval.latitude, raval.longitude) == (41.38, 2.17)
