#!/usr/bin/env python3
"""
Courier Route Optimization Bot
Telegram bot for optimizing delivery routes with real-time traffic consideration
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.bot.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
