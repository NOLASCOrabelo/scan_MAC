import unittest
import os
import json
import random
import sys
import math
from random_timer import RandomTimer, ActionType, TimerConfig, DelayRange

class TestRandomTimer(unittest.TestCase):
    def setUp(self):
        self.config_path = "test_timer_config.json"
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_property_1_range_validation(self):
        """Feature: comportamento-humano-aleatorio, Property 1: Range validation"""
        timer = RandomTimer(config_path=self.config_path)
        for _ in range(100):
            min_val = random.uniform(0.1, 5.0)
            max_val = min_val + random.uniform(0.1, 5.0)
            delay = timer.get_delay(ActionType.POST_PROCESSING, min_val, max_val)
            self.assertTrue(min_val <= delay <= max_val)

    def test_property_2_unit_conversion_consistency(self):
        """Feature: comportamento-humano-aleatorio, Property 2: Unit conversion consistency"""
        timer = RandomTimer(config_path=self.config_path)
        # Test 100 iterations of converting between minutes and seconds
        for _ in range(100):
            min_val_min = random.uniform(0.01, 0.1) # in minutes
            max_val_min = min_val_min + random.uniform(0.01, 0.1)
            
            # get_delay with minutes unit
            delay_sec_from_min = timer.get_delay(ActionType.POST_PROCESSING, min_val_min, max_val_min, unit="minutes") * 60.0
            
            # The generated delay in seconds should be between the bounds converted to seconds
            self.assertTrue(min_val_min * 60.0 <= delay_sec_from_min <= max_val_min * 60.0)

    def test_property_3_logging_completeness(self):
        """Feature: comportamento-humano-aleatorio, Property 3: Logging completeness"""
        logged_entries = []
        def custom_log(msg, level):
            logged_entries.append((msg, level))

        timer = RandomTimer(config_path=self.config_path, log_callback=custom_log)
        
        # Test 100 iterations of logging completeness
        for i in range(100):
            timer.sleep_random(ActionType.SHORT_WAIT)
            self.assertEqual(len(logged_entries), i + 1)
            msg, level = logged_entries[-1]
            self.assertEqual(level, "info")
            self.assertIn("short_wait", msg)
            self.assertIn("range:", msg)

    def test_property_4_delay_randomness(self):
        """Feature: comportamento-humano-aleatorio, Property 4: Delay randomness"""
        timer = RandomTimer(config_path=self.config_path)
        delays = []
        # Generate 100 delays to test variance and distribution
        for _ in range(100):
            delay = timer.get_delay(ActionType.POST_PROCESSING, 1.0, 5.0)
            delays.append(delay)
            self.assertTrue(1.0 <= delay <= 5.0)
        
        # Check standard deviation to verify we don't have clustering or patterns
        mean = sum(delays) / len(delays)
        variance = sum((x - mean) ** 2 for x in delays) / len(delays)
        std_dev = math.sqrt(variance)
        
        # Expected standard deviation for uniform distribution U(1, 5) is (5-1)/sqrt(12) approx 1.15
        # It should be well above 0.5 under standard random conditions
        self.assertGreater(std_dev, 0.5)

    def test_property_5_contextual_range_application(self):
        """Feature: comportamento-humano-aleatorio, Property 5: Contextual range application"""
        timer = RandomTimer(config_path=self.config_path)
        # Test 100 iterations across different ActionTypes
        action_types = list(ActionType)
        for _ in range(100):
            a_type = random.choice(action_types)
            cfg_range = timer.get_configured_range(a_type)
            delay = timer.get_delay(a_type)
            self.assertTrue(cfg_range.min_seconds <= delay <= cfg_range.max_seconds)

    def test_property_6_configuration_loading(self):
        """Feature: comportamento-humano-aleatorio, Property 6: Configuration loading"""
        # Save a custom config, and load it, repeating 100 times with random configurations
        for _ in range(100):
            custom_enabled = random.choice([True, False])
            custom_min = random.uniform(0.5, 2.0)
            custom_max = custom_min + random.uniform(1.0, 3.0)
            
            data = {
                "enabled": custom_enabled,
                "delay_ranges": {
                    "post_processing": {"min_seconds": custom_min, "max_seconds": custom_max}
                }
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
                
            timer = RandomTimer(config_path=self.config_path)
            self.assertEqual(timer.is_enabled(), custom_enabled)
            rng = timer.get_configured_range(ActionType.POST_PROCESSING)
            self.assertAlmostEqual(rng.min_seconds, custom_min)
            self.assertAlmostEqual(rng.max_seconds, custom_max)

    def test_property_7_input_validation(self):
        """Feature: comportamento-humano-aleatorio, Property 7: Input validation"""
        timer = RandomTimer(config_path=self.config_path)
        # Test 100 iterations of invalid inputs
        for _ in range(100):
            # Test min >= max
            bad_min = random.uniform(2.0, 5.0)
            bad_max = bad_min - random.uniform(0.1, 1.0)
            validated = timer.validate_range(DelayRange(bad_min, bad_max), DelayRange(1.0, 5.0), "test")
            self.assertEqual(validated.min_seconds, 1.0)
            self.assertEqual(validated.max_seconds, 5.0)
            
            # Test negative values
            neg_min = -random.uniform(0.1, 5.0)
            neg_max = -random.uniform(0.1, 5.0)
            # Ensure min < max to avoid min >= max triggering first
            if neg_min > neg_max:
                neg_min, neg_max = neg_max, neg_min
            validated = timer.validate_range(DelayRange(neg_min, neg_max), DelayRange(1.0, 5.0), "test")
            self.assertGreaterEqual(validated.min_seconds, 0.001)
            self.assertGreaterEqual(validated.max_seconds, 0.001)

    def test_property_8_typing_simulation_randomness(self):
        """Feature: comportamento-humano-aleatorio, Property 8: Typing simulation randomness"""
        timer = RandomTimer(config_path=self.config_path)
        # Test 100 character delay generations
        char_delays = []
        for _ in range(100):
            delay = timer.get_delay(ActionType.TYPING_CHAR)
            char_delays.append(delay)
            self.assertTrue(0.015 <= delay <= 0.050)
            
        # Standard deviation for U(0.015, 0.050) is approx 0.010
        mean = sum(char_delays) / len(char_delays)
        variance = sum((x - mean) ** 2 for x in char_delays) / len(char_delays)
        std_dev = math.sqrt(variance)
        self.assertGreater(std_dev, 0.005)

    def test_example_enable_disable(self):
        # When disabled, get_delay returns the legacy fixed value
        data = {
            "enabled": False,
            "delay_ranges": {}
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
        timer = RandomTimer(config_path=self.config_path)
        self.assertFalse(timer.is_enabled())
        # Fixed delay for post_processing is 2.0
        self.assertEqual(timer.get_delay(ActionType.POST_PROCESSING), 2.0)
        # Fixed delay for feed_loading is 10.0
        self.assertEqual(timer.get_delay(ActionType.FEED_LOADING), 10.0)

    def test_malformed_json_fallback(self):
        # Write malformed JSON
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json")
            
        # Instantiating should not fail, should fallback to defaults
        timer = RandomTimer(config_path=self.config_path)
        self.assertTrue(timer.is_enabled())
        self.assertEqual(timer.get_configured_range(ActionType.POST_PROCESSING).min_seconds, 1.0)
        
        # File should have been recreated
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["enabled"])

if __name__ == "__main__":
    unittest.main()
