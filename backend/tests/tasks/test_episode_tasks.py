"""
Smoke tests for Celery tasks to ensure they're wired correctly.
"""

from unittest.mock import patch


class TestTaskWiring:
    """Verify tasks call the correct commands."""

    @patch("commands.ingest_data.ingest_data")
    def test_ingest_task_calls_command(self, mock_ingest):
        """Verify ingest_data_task calls the ingest_data command."""
        from tasks.episode_tasks import ingest_data_task

        result = ingest_data_task()

        mock_ingest.assert_called_once()
        assert result["status"] == "success"

    @patch("commands.classify_episodes.classify_episodes")
    def test_classify_task_calls_command(self, mock_classify):
        from tasks.episode_tasks import classify_episodes_task

        result = classify_episodes_task(batch_size=10, max_total=100)

        mock_classify.assert_called_once_with(batch_size=10, max_total=100)
        assert result["status"] == "success"
        assert result["batch_size"] == 10
        assert result["max_total"] == 100

    @patch("tasks.episode_tasks.chain")
    @patch("tasks.episode_tasks.ingest_data_task")
    @patch("tasks.episode_tasks.classify_episodes_task")
    def test_chain_wiring(self, mock_classify, mock_ingest, mock_chain):
        """Verify the chain creates the correct workflow."""
        from unittest.mock import MagicMock

        from tasks.episode_tasks import ingest_and_classify_chain

        # Arrange
        mock_workflow = MagicMock()
        mock_workflow.apply_async.return_value = MagicMock(id="test-id")
        mock_chain.return_value = mock_workflow

        mock_ingest.s.return_value = MagicMock()
        mock_classify.s.return_value = MagicMock()

        # Act
        result = ingest_and_classify_chain(batch_size=25)

        # Assert
        mock_chain.assert_called_once()
        assert result["status"] == "Chained workflow started"
        assert "chain_id" in result

    @patch("commands.backfill_embeddings.backfill_embeddings")
    def test_embeddings_task_re_embeds_the_episodes_asked_for(
        self, mock_backfill
    ):
        from tasks.episode_tasks import generate_embeddings_task

        generate_embeddings_task(episode_ids=[1, 2], refresh=True)

        mock_backfill.assert_called_once_with(
            batch_size=100, max_total=None, refresh=True, episode_ids=[1, 2]
        )

    @patch("commands.link_wikipedia_articles.link_wikipedia_articles")
    def test_link_wikipedia_task_calls_command(self, mock_link):
        from tasks.episode_tasks import link_wikipedia_articles_task

        result = link_wikipedia_articles_task(batch_size=1, max_total=1)

        mock_link.assert_called_once_with(
            batch_size=1, max_total=1, episode_ids=None
        )
        assert result["status"] == "success"

    @patch("commands.link_wikipedia_articles.link_wikipedia_articles")
    def test_link_wikipedia_task_links_the_episodes_asked_for(self, mock_link):
        from tasks.episode_tasks import link_wikipedia_articles_task

        link_wikipedia_articles_task(episode_ids=[1, 2])

        mock_link.assert_called_once_with(
            batch_size=50, max_total=None, episode_ids=[1, 2]
        )

    @patch("tasks.episode_tasks.chain")
    def test_chain_links_wikipedia_last_with_the_same_cap(self, mock_chain):
        from tasks.episode_tasks import ingest_and_classify_chain

        mock_chain.return_value.apply_async.return_value.id = "test-id"

        ingest_and_classify_chain(batch_size=1, max_total=1)

        steps = mock_chain.call_args.args
        assert [step.task for step in steps] == [
            "tasks.episode_tasks.ingest_data_task",
            "tasks.episode_tasks.classify_episodes_task",
            "tasks.episode_tasks.generate_embeddings_task",
            "tasks.episode_tasks.link_wikipedia_articles_task",
        ]
        assert steps[-1].kwargs == {"batch_size": 1, "max_total": 1}
