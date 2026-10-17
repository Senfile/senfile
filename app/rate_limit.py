"""
Limitation de débit basée sur l'IP du client, via slowapi (wrapper de limits).
Protège les routes sensibles (login, register, upload) contre le brute-force /
l'abus, indépendamment de toute protection au niveau du reverse proxy / WAF.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
