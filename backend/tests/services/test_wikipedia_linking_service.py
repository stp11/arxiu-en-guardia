import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from models import Category, CategoryType, Episode
from repositories import IEpisodesRepository, IWikipediaArticlesRepository
from services import WikipediaLinkingService
from wikipedia import Article


class FakeOpenAI:
    """Answers each completion with the next canned result."""

    def __init__(self, *results: dict):
        self.results = list(results)
        self.prompts = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._complete)
        )

    def _complete(self, messages, **kwargs):
        self.prompts.append(messages[0]["content"])
        content = json.dumps(self.results.pop(0))
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeWikipedia:
    def __init__(self, titles=None, results=None):
        self.titles = titles or {}
        self.results = results or {}
        self.searched = []

    def lookup(self, titles):
        return {title: self.titles.get(title) for title in titles}

    def search(self, text, limit):
        self.searched.append(text)
        return self.results.get(text, [])[:limit]


def article(title: str, **kwargs) -> Article:
    url = "https://ca.wikipedia.org/wiki/" + title.replace(" ", "_")
    return Article(title=title, url=url, **kwargs)


SEGADORS = article("Guerra dels Segadors")
CLARIS = article("Pau Claris")
JAUME = article("Jaume el Conqueridor")
SUCCESSIO = article("Guerra de Successió", disambiguation=True)
SUCCESSIO_ESPANYOLA = article("Guerra de Successió Espanyola")
SUCCESSIO_POLONESA = article("Guerra de Successió de Polònia")


class TestWikipediaLinkingService:
    def setup_method(self):
        self.episode = Episode(
            id=1,
            title="Els herois de la guerra de Successió",
            description="Capítol 302. Els defensors de Barcelona el 1714.",
            categories=[
                Category(
                    name="Guerra de Successió",
                    slug="guerra-de-successio",
                    type=CategoryType.TOPIC,
                )
            ],
        )

    def service(self, openai, wikipedia) -> WikipediaLinkingService:
        self.episodes_repository = MagicMock(spec=IEpisodesRepository)
        self.articles_repository = MagicMock(spec=IWikipediaArticlesRepository)
        return WikipediaLinkingService(
            openai,
            wikipedia,
            self.episodes_repository,
            self.articles_repository,
        )

    def test_keeps_the_articles_wikipedia_confirms(self):
        openai = FakeOpenAI(
            {"articles": ["Guerra dels Segadors", "Pau Claris"]}
        )
        wikipedia = FakeWikipedia(
            titles={"Guerra dels Segadors": SEGADORS, "Pau Claris": CLARIS}
        )

        articles = self.service(openai, wikipedia).find_articles(self.episode)

        assert articles == [SEGADORS, CLARIS]
        assert wikipedia.searched == []
        assert len(openai.prompts) == 1
        assert "Els defensors de Barcelona" in openai.prompts[0]
        assert "Guerra de Successió" in openai.prompts[0]

    def test_keeps_one_article_for_names_that_lead_to_it(self):
        openai = FakeOpenAI({"articles": ["Jaume I", "Jaume el Conqueridor"]})
        wikipedia = FakeWikipedia(
            titles={"Jaume I": JAUME, "Jaume el Conqueridor": JAUME}
        )

        articles = self.service(openai, wikipedia).find_articles(self.episode)

        assert articles == [JAUME]

    def test_caps_and_cleans_the_proposed_names(self):
        openai = FakeOpenAI({"articles": [" A ", "A", "", "B", "C", "D"]})
        wikipedia = FakeWikipedia(
            titles={name: article(name) for name in "ABCD"}
        )

        articles = self.service(openai, wikipedia).find_articles(self.episode)

        assert [a.title for a in articles] == ["A", "B", "C"]

    def test_picks_from_the_search_when_a_name_is_not_an_article(self):
        openai = FakeOpenAI(
            {"articles": ["Guerra de Successió", "Herois del 1714", "Pau"]},
            {
                "choices": [
                    {"id": 1, "title": "Guerra de Successió Espanyola"},
                    {"id": 2, "title": None},
                ]
            },
        )
        wikipedia = FakeWikipedia(
            titles={"Guerra de Successió": SUCCESSIO, "Pau": CLARIS},
            results={
                "Guerra de Successió": [
                    SUCCESSIO,
                    SUCCESSIO_POLONESA,
                    SUCCESSIO_ESPANYOLA,
                ],
                "Herois del 1714": [SEGADORS],
            },
        )

        articles = self.service(openai, wikipedia).find_articles(self.episode)

        assert articles == [SUCCESSIO_ESPANYOLA, CLARIS]
        assert wikipedia.searched == ["Guerra de Successió", "Herois del 1714"]
        choices_prompt = openai.prompts[1]
        assert '[1] "Guerra de Successió"' in choices_prompt
        assert '- "Guerra de Successió de Polònia"' in choices_prompt
        assert '- "Guerra de Successió"\n' not in choices_prompt

    def test_ignores_a_choice_outside_the_results(self):
        openai = FakeOpenAI(
            {"articles": ["Guerra de Successió"]},
            {"choices": [{"id": 1, "title": "Guerra de Successió Austríaca"}]},
        )
        wikipedia = FakeWikipedia(
            titles={"Guerra de Successió": SUCCESSIO},
            results={"Guerra de Successió": [SUCCESSIO_ESPANYOLA]},
        )

        articles = self.service(openai, wikipedia).find_articles(self.episode)

        assert articles == []

    def test_skips_the_choice_when_the_search_finds_nothing(self):
        openai = FakeOpenAI({"articles": ["Herois del 1714"]})
        wikipedia = FakeWikipedia()

        articles = self.service(openai, wikipedia).find_articles(self.episode)

        assert articles == []
        assert len(openai.prompts) == 1

    def test_saves_the_links_and_marks_the_episode_checked(self):
        service = self.service(FakeOpenAI(), FakeWikipedia())
        self.articles_repository.get_or_create_article.side_effect = [
            SimpleNamespace(id=10),
            SimpleNamespace(id=11),
        ]

        service.save_articles(self.episode, [SEGADORS, CLARIS])

        self.articles_repository.get_or_create_article.assert_any_call(
            "Pau Claris", CLARIS.url
        )
        links = self.episodes_repository.link_episode_to_article.call_args_list
        assert [call.args for call in links] == [(1, 10), (1, 11)]
        assert self.episode.wikipedia_checked_at is not None
        assert self.episode.wikipedia_checked_at.tzinfo is None
