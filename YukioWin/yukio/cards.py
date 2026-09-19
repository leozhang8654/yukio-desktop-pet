"""雪绪头顶那摞通知卡里的一张：一条聊天一张。

取自 ChatGPT 桌面版那只宠物的做法：多个聊天同时跑时不逼你二选一，
谁在等你、谁出错、谁答完了各挂一张卡，点哪张去哪条聊天。
她自己显示的那条不在这叠里——头顶气泡已经在讲它。

移植自 YukioPlayer/Sources/YukioCore/ActivityCards.swift。
"""

from __future__ import annotations

from typing import NamedTuple


class CardStatus:
    """卡的状态，也是排序的档位：等你回答 → 出错停住 → 答完了 → 还在干活。"""

    waiting = "waiting"
    failed = "failed"
    ready = "ready"
    running = "running"

    ALL = (waiting, failed, ready, running)

    #: 越小越先看。
    RANK = {waiting: 0, failed: 1, ready: 2, running: 3}
    #: 卡右上角的短标签。
    LABEL = {waiting: "等你回答", failed: "出错", ready: "答完了", running: "在跑"}

    @staticmethod
    def rank(status: str) -> int:
        return CardStatus.RANK[status]

    @staticmethod
    def label(status: str) -> str:
        return CardStatus.LABEL[status]


class ActivityCard(NamedTuple):
    #: 会话 ID：点这张卡就用它去找对应的聊天。
    session: str
    #: 聊天名：会话标题或请求第一行，都没有时用会话 ID 前 8 位。
    title: str
    #: 第二行：正在做什么，或在等什么。
    subtitle: str
    #: CardStatus 里的一种。
    status: str
    #: 距最近一次事件多久（毫秒）。
    quiet_ms: float

    @property
    def rank(self) -> int:
        return CardStatus.rank(self.status)

    @property
    def status_label(self) -> str:
        return CardStatus.label(self.status)
