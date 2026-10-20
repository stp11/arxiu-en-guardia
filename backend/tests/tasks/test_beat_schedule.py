from tasks.main import beat_schedule


class TestBeatSchedule:
    def test_backs_up_outside_local(self):
        schedule = beat_schedule(local=False)

        assert "backup-database-weekly" in schedule
        assert "ingest-and-classify-weekly" in schedule

    def test_never_backs_up_locally(self):
        schedule = beat_schedule(local=True)

        assert "backup-database-weekly" not in schedule
        assert "ingest-and-classify-weekly" in schedule
