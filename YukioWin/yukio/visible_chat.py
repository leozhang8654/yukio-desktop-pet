"""Exact chat identity from a visible document address; never infer from a title."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit, parse_qs, unquote
from uuid import UUID


def normalize_id(value):
    try:
        # Match Foundation UUID's canonical, hyphenated representation.
        if len(value) == 36:
            return str(UUID(value))
    except ValueError:
        pass
    if re.fullmatch(r'(?:local_|session_|cse_|task_)[A-Za-z0-9_-]+', value) and 12 <= len(value) <= 100:
        return value
    return None


@dataclass(frozen=True)
class VisibleChat:
    provider: str
    id: str

    @classmethod
    def from_url(cls, text):
        try:
            url = urlsplit(text)
            if url.username is not None or url.password is not None or url.port is not None:
                return None
            path = [unquote(p) for p in url.path.split('/') if p]
            identity = None
            if url.scheme == 'https' and url.hostname == 'claude.ai':
                provider = 'claude'
                if len(path) == 2 and path[0] in ('chat', 'code', 'cowork', 'epitaxy'):
                    identity = path[1]
                if len(path) == 3 and path[:2] == ['cic', 'task']:
                    identity = path[2]
            elif url.scheme == 'https' and url.hostname in ('chatgpt.com', 'chat.openai.com'):
                provider = 'gpt'
                if len(path) == 2 and path[0] == 'c':
                    identity = path[1]
                if len(path) == 4 and path[0] == 'g' and path[2] == 'c':
                    identity = path[3]
                if len(path) == 3 and path[:2] == ['codex', 'tasks']:
                    identity = path[2]
            elif url.scheme == 'codex' and url.hostname == 'threads' and len(path) == 1:
                provider, identity = 'gpt', path[0]
            elif url.scheme == 'claude' and url.hostname == 'code' and path == ['continue']:
                provider = 'claude'
                ids = parse_qs(url.query).get('session', [])
                if len(ids) == 1:
                    identity = ids[0]
            else:
                return None
            identity = normalize_id(identity or '')
            return cls(provider, identity) if identity else None
        except (ValueError, TypeError):
            return None

    def matches(self, session, provider, aliases=None):
        return self.provider == provider and (self.id == (normalize_id(session) or session)
                                               or (aliases or {}).get(self.id) == session)
