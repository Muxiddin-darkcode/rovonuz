"""
ROVON.UZ - Core Runtime System State
Holds global runtime variables shared across background workers and the Telegram bot.
"""

# Global Emergency Kill-Switch State
IS_EMERGENCY_STOP_ACTIVE: bool = False
