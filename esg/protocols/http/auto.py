import asyncio
from typing import Type

from esg.protocols.http.protocol import Protocol

AutoHTTPProtocol: Type[asyncio.Protocol] = Protocol
