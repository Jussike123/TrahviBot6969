import asyncio
import unittest
from unittest.mock import patch

import bot


class FakeLoop:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now


class PollForArrivalTests(unittest.TestCase):
    def test_poll_for_arrival_defaults_to_five_minutes(self):
        loop = FakeLoop()

        async def fake_sleep(delay):
            loop.now += delay

        async def fake_get_player_location(username):
            raise RuntimeError('location unavailable')

        with patch.object(bot.asyncio, 'get_event_loop', return_value=loop), \
             patch.object(bot.asyncio, 'sleep', side_effect=fake_sleep), \
             patch.object(bot.erlc_client, 'get_player_location', side_effect=fake_get_player_location):
            arrived, alert_triggered = asyncio.run(
                bot.poll_for_arrival('tester', {'zip': '205'}, interaction=None)
            )

        self.assertFalse(arrived)
        self.assertFalse(alert_triggered)
        self.assertEqual(loop.now, 300.0)

    def test_ensure_player_stays_reports_remaining_minutes(self):
        loop = FakeLoop()

        async def fake_sleep(delay):
            loop.now += delay

        async def fake_get_player_location(username):
            return {'zip': '205'}

        class FakeFollowup:
            def __init__(self):
                self.messages = []

            async def send(self, message, ephemeral=False):
                self.messages.append((message, ephemeral))

        class FakeInteraction:
            def __init__(self):
                self.followup = FakeFollowup()
                self.messages = self.followup.messages

        interaction = FakeInteraction()

        with patch.object(bot.asyncio, 'get_event_loop', return_value=loop), \
             patch.object(bot.asyncio, 'sleep', side_effect=fake_sleep), \
             patch.object(bot.erlc_client, 'get_player_location', side_effect=fake_get_player_location):
            stayed = asyncio.run(
                bot.ensure_player_stays(1, 'tester', {'zip': '205'}, 120, interaction=interaction, check_interval=2.0)
            )

        self.assertTrue(stayed)
        self.assertIn(('Jäänud aeg: 2 minutit', True), interaction.messages)


if __name__ == '__main__':
    unittest.main()
