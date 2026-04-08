from __future__ import annotations


class KnowledgeError(Exception):
    pass


class ConfigurationError(KnowledgeError):
    pass


class ProviderError(KnowledgeError):
    pass


class AuthError(KnowledgeError):
    pass
