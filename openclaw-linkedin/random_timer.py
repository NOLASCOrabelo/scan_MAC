import os
import json
import random
import time
import sys
from enum import Enum
from dataclasses import dataclass

class ActionType(Enum):
    POST_PROCESSING = "post_processing"
    FEED_LOADING = "feed_loading"
    SCROLL_DELAY = "scroll_delay"
    REACTION_TO_COMMENT = "reaction_to_comment"
    TYPING_CHAR = "typing_char"
    SHORT_WAIT = "short_wait"
    MEDIUM_WAIT = "medium_wait"
    LONG_WAIT = "long_wait"
    COMMENT_SUBMISSION = "comment_submission"

class DelayRange:
    def __init__(self, min_seconds: float, max_seconds: float):
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds

class TimerConfig:
    def __init__(self, enabled: bool = True,
                 post_processing = None,
                 feed_loading = None,
                 scroll_delays = None,
                 reaction_to_comment = None,
                 typing_per_char = None,
                 short_waits = None,
                 medium_waits = None,
                 long_waits = None,
                 comment_submission = None):
        self.enabled = enabled
        self.post_processing = post_processing or DelayRange(1.0, 5.0)
        self.feed_loading = feed_loading or DelayRange(8.0, 15.0)
        self.scroll_delays = scroll_delays or DelayRange(1.0, 4.0)
        self.reaction_to_comment = reaction_to_comment or DelayRange(2.0, 8.0)
        self.typing_per_char = typing_per_char or DelayRange(0.015, 0.050)
        self.short_waits = short_waits or DelayRange(0.5, 2.0)
        self.medium_waits = medium_waits or DelayRange(2.0, 5.0)
        self.long_waits = long_waits or DelayRange(5.0, 10.0)
        self.comment_submission = comment_submission or DelayRange(1.0, 3.0)

def load_from_dict(data: dict) -> TimerConfig:
    config = TimerConfig()
    config.enabled = data.get("enabled", True)
    ranges = data.get("delay_ranges", {})
    
    def get_range(key, aliases, default):
        for k in [key] + aliases:
            if k in ranges:
                val = ranges[k]
                if isinstance(val, dict):
                    min_val = val.get("min_seconds")
                    max_val = val.get("max_seconds")
                    if min_val is not None and max_val is not None:
                        return DelayRange(float(min_val), float(max_val))
        return default
        
    config.post_processing = get_range("post_processing", [], DelayRange(1.0, 5.0))
    config.feed_loading = get_range("feed_loading", [], DelayRange(8.0, 15.0))
    config.scroll_delays = get_range("scroll_delay", ["scroll_delays"], DelayRange(1.0, 4.0))
    config.reaction_to_comment = get_range("reaction_to_comment", [], DelayRange(2.0, 8.0))
    config.typing_per_char = get_range("typing_char", ["typing_per_char"], DelayRange(0.015, 0.050))
    config.short_waits = get_range("short_wait", ["short_waits"], DelayRange(0.5, 2.0))
    config.medium_waits = get_range("medium_wait", ["medium_waits"], DelayRange(2.0, 5.0))
    config.long_waits = get_range("long_wait", ["long_waits"], DelayRange(5.0, 10.0))
    config.comment_submission = get_range("comment_submission", [], DelayRange(1.0, 3.0))
    return config

class RandomTimer:
    def __init__(self, config_path: str = "timer_config.json", log_callback=None):
        self.config_path = config_path
        self.log_callback = log_callback
        self.config = self.load_config()
        
    def _log_direct(self, message: str, level: str = "info"):
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except Exception as e:
                print(f"Logging callback failed: {e}", file=sys.stderr)
                raise e
        else:
            print(f"[{level.upper()}] {message}")

    def validate_range(self, r: DelayRange, default: DelayRange, name: str) -> DelayRange:
        min_val = r.min_seconds
        max_val = r.max_seconds
        
        clamped = False
        if min_val < 0.001:
            min_val = 0.001
            clamped = True
        if max_val < 0.001:
            max_val = 0.001
            clamped = True
            
        if clamped:
            self._log_direct(f"Value for {name} was negative, clamped to 0.001", "warning")
            
        if min_val >= max_val:
            self._log_direct(
                f"Invalid range for {name}: min ({min_val}) >= max ({max_val}). Using default {default.min_seconds}-{default.max_seconds}",
                "error"
            )
            return default
            
        return DelayRange(min_val, max_val)

    def load_config(self) -> TimerConfig:
        default_config = TimerConfig()
        if not os.path.exists(self.config_path):
            self.save_config(default_config)
            return default_config
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = load_from_dict(data)
            
            # Validate ranges
            config.post_processing = self.validate_range(config.post_processing, default_config.post_processing, "post_processing")
            config.feed_loading = self.validate_range(config.feed_loading, default_config.feed_loading, "feed_loading")
            config.scroll_delays = self.validate_range(config.scroll_delays, default_config.scroll_delays, "scroll_delay")
            config.reaction_to_comment = self.validate_range(config.reaction_to_comment, default_config.reaction_to_comment, "reaction_to_comment")
            config.typing_per_char = self.validate_range(config.typing_per_char, default_config.typing_per_char, "typing_char")
            config.short_waits = self.validate_range(config.short_waits, default_config.short_waits, "short_wait")
            config.medium_waits = self.validate_range(config.medium_waits, default_config.medium_waits, "medium_wait")
            config.long_waits = self.validate_range(config.long_waits, default_config.long_waits, "long_wait")
            config.comment_submission = self.validate_range(config.comment_submission, default_config.comment_submission, "comment_submission")
            
            return config
        except json.JSONDecodeError as e:
            self._log_direct(f"Malformed JSON config: {e}. Recreating with defaults.", "error")
            self.save_config(default_config)
            return default_config
        except Exception as e:
            self._log_direct(f"Error loading config: {e}. Using defaults.", "error")
            return default_config

    def save_config(self, config: TimerConfig):
        data = {
            "enabled": config.enabled,
            "delay_ranges": {
                "post_processing": {"min_seconds": config.post_processing.min_seconds, "max_seconds": config.post_processing.max_seconds},
                "feed_loading": {"min_seconds": config.feed_loading.min_seconds, "max_seconds": config.feed_loading.max_seconds},
                "scroll_delay": {"min_seconds": config.scroll_delays.min_seconds, "max_seconds": config.scroll_delays.max_seconds},
                "reaction_to_comment": {"min_seconds": config.reaction_to_comment.min_seconds, "max_seconds": config.reaction_to_comment.max_seconds},
                "typing_char": {"min_seconds": config.typing_per_char.min_seconds, "max_seconds": config.typing_per_char.max_seconds},
                "short_wait": {"min_seconds": config.short_waits.min_seconds, "max_seconds": config.short_waits.max_seconds},
                "medium_wait": {"min_seconds": config.medium_waits.min_seconds, "max_seconds": config.medium_waits.max_seconds},
                "long_wait": {"min_seconds": config.long_waits.min_seconds, "max_seconds": config.long_waits.max_seconds},
                "comment_submission": {"min_seconds": config.comment_submission.min_seconds, "max_seconds": config.comment_submission.max_seconds}
            }
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self._log_direct(f"Failed to save config file: {e}", "error")

    def get_configured_range(self, action_type: ActionType) -> DelayRange:
        ranges = {
            ActionType.POST_PROCESSING: self.config.post_processing,
            ActionType.FEED_LOADING: self.config.feed_loading,
            ActionType.SCROLL_DELAY: self.config.scroll_delays,
            ActionType.REACTION_TO_COMMENT: self.config.reaction_to_comment,
            ActionType.TYPING_CHAR: self.config.typing_per_char,
            ActionType.SHORT_WAIT: self.config.short_waits,
            ActionType.MEDIUM_WAIT: self.config.medium_waits,
            ActionType.LONG_WAIT: self.config.long_waits,
            ActionType.COMMENT_SUBMISSION: self.config.comment_submission
        }
        return ranges.get(action_type, DelayRange(1.0, 2.0))

    def get_fixed_delay(self, action_type: ActionType, unit: str = "seconds") -> float:
        fixed_delays = {
            ActionType.POST_PROCESSING: 2.0,
            ActionType.FEED_LOADING: 10.0,
            ActionType.SCROLL_DELAY: 2.0,
            ActionType.REACTION_TO_COMMENT: 0.0,
            ActionType.TYPING_CHAR: 0.020,
            ActionType.SHORT_WAIT: 1.0,
            ActionType.MEDIUM_WAIT: 3.0,
            ActionType.LONG_WAIT: 5.0,
            ActionType.COMMENT_SUBMISSION: 2.0
        }
        val = fixed_delays.get(action_type, 1.0)
        if unit == "minutes":
            return val / 60.0
        return val

    def is_enabled(self) -> bool:
        return self.config.enabled

    def get_delay(self, action_type: ActionType, min_time: float = None, max_time: float = None, unit: str = "seconds") -> float:
        if not self.config.enabled:
            return self.get_fixed_delay(action_type, unit)
            
        cfg_range = self.get_configured_range(action_type)
        
        # Scale range boundaries from minutes to seconds if input is in minutes
        if unit == "minutes":
            min_val = min_time * 60.0 if min_time is not None else cfg_range.min_seconds
            max_val = max_time * 60.0 if max_time is not None else cfg_range.max_seconds
        else:
            min_val = min_time if min_time is not None else cfg_range.min_seconds
            max_val = max_time if max_time is not None else cfg_range.max_seconds

        # Clamp override boundaries
        if min_val < 0.001:
            min_val = 0.001
        if max_val < 0.001:
            max_val = 0.001

        if min_val >= max_val:
            self._log_direct(f"Override range is invalid: min ({min_val}) >= max ({max_val}). Using config range.", "warning")
            min_val = cfg_range.min_seconds
            max_val = cfg_range.max_seconds

        try:
            val = random.uniform(min_val, max_val)
        except Exception as e:
            self._log_direct(f"Random generation failed: {e}. Falling back to midpoint.", "error")
            val = (min_val + max_val) / 2.0

        if unit == "minutes":
            return val / 60.0
        return val

    def sleep_random(self, action_type: ActionType, min_time: float = None, max_time: float = None, unit: str = "seconds") -> None:
        delay = self.get_delay(action_type, min_time, max_time, unit)
        sleep_seconds = delay * 60.0 if unit == "minutes" else delay
        
        cfg_range = self.get_configured_range(action_type)
        min_range = min_time if min_time is not None else cfg_range.min_seconds
        max_range = max_time if max_time is not None else cfg_range.max_seconds
        if unit == "minutes" and min_time is None:
            min_range = min_range / 60.0
            max_range = max_range / 60.0

        mode_str = "random" if self.config.enabled else "fixed"
        log_message = f"Sleeping for {delay:.3f} {unit} ({mode_str} delay, range: {min_range}-{max_range} {unit}) for action {action_type.value}"

        try:
            self._log_direct(log_message, "info")
        except Exception as e:
            print(f"Logging failed: {e}", file=sys.stderr)
            if action_type == ActionType.POST_PROCESSING:
                raise e

        time.sleep(sleep_seconds)
