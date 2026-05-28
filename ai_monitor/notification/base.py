# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import List


class AbstractNotificationChannel(ABC):
    name: str = "base"

    @abstractmethod
    async def send(
        self,
        title: str,
        body: str,
        severity: str = "warning",
    ) -> bool:
        """Send notification. Returns True on success."""
