import asyncio
from typing import Optional
from loguru import logger

class ConnectionError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class TCPClient:
    """
    Simple TCP Client that wraps asyncio stream.

    All methods are wrappers around asyncio stream methods with added logging, simplified timeout
        setup, and error handling.

    Attributes:
        logger (loguru.Logger): Internal logger.
        ip (str): IP Address of TCP Socket.
        port (int): Port number for TCP Socket.
        _stream_reader (asyncio.StreamReader): Internal StreamReader object for streaming connection.
        _stream_writer (asyncio.StreamWriter): Internal StreamWriter object for streaming connection.
    """
    def __init__(self, ip: str, port: int):
        self.logger = logger
        self.ip: str = ip
        self.port: int = port
        self._stream_reader: Optional[asyncio.StreamReader] = None
        self._stream_writer: Optional[asyncio.StreamWriter] = None


    async def open_connection(self, connect_timeout_s: float = 10.0) -> None:
        """
        Opens TCP socket.

        If stream_writer and stream_reader already exist, does nothing. If they do not,
            opens connection with specified timeout limit and sets stream_writer and
            stream_reader attributes.

        Args:
            connect_timeout_s (float, optional): Timeout in seconds to wait for ROC to accept connection. Defaults to 10.0.

        Raises:
            ConnectionError: Re-raises socket.error or other Exception while connecting to device.
        """
        self.logger.debug('Ensuring ROC Client connection.')
        if self._stream_reader is None or self._stream_writer is None:
            try:
                self.logger.debug('Stream does not exist. Opening connection...')
                async with asyncio.timeout(connect_timeout_s):
                    reader, writer = await asyncio.open_connection(
                        host=self.ip,
                        port=self.port
                    )
                    self._stream_reader = reader
                    self._stream_writer = writer
                    self.logger.debug('Stream connected successfully.')
                return
            except Exception as e:
                raise ConnectionError(f'Error while connecting to device: {e}')
        else:
            self.logger.debug('Stream already exists.')
        return
    

    async def close_connection(self, close_timeout_s: float = 1.0) -> None:
        """
        Close TCP socket.

        If stream_writer exists, wait for connection to close with specified timeout limit. Re-initializes both
            stream_writer and stream_reader attributes to None.

        Args:
            close_timeout_s (int, optional): Timeout in seconds to wait for connection to close. Defaults to 1.0.

        Raises:
            ConnectionError: Timed out waiting for connection to close or encountered socket.error while closing.
        """
        self.logger.debug('Closing connection.')
        if self._stream_writer:
            try:
                self.logger.debug('Stream writer exists. Closing...')
                async with asyncio.timeout(close_timeout_s):
                    self._stream_writer.close()
                    await self._stream_writer.wait_closed()
                self.logger.debug('Stream write closed.')
            except asyncio.TimeoutError:
                raise ConnectionError('Timed out waiting for connection to close.')
            except Exception as e:
                raise ConnectionError(f'Socket error while closing connection: {e}')
        self._stream_reader = None
        self._stream_writer = None
        self.logger.debug('Stream destroyed.')
        return
    

    async def write_to_stream(self, data: bytes, write_timeout_s: float = 1.0) -> None:
        """
        Write bytes to ROC socket stream.

        Verifies connection is open, writes bytes to stream, and flushes the write buffer.

        Args:
            data (bytes): Raw data to write to stream.
            write_timeout_s (float, optional): Timeout in seconds to wait for write buffer to flush. Defaults to 1.0.

        Raises:
            ConnectionError: Timed out waiting for write to complete, socket.error while writing, or stream_writer is null.
        """
        self.logger.debug('Checking connection status.')
        await self.open_connection()
        if self._stream_writer:
            try:
                self.logger.debug('Writing to stream...')
                async with asyncio.timeout(write_timeout_s):
                    self._stream_writer.write(data)
                    await self._stream_writer.drain()
                    self.logger.debug('Data written to stream successfully.')
                    self.logger.trace(f'Request: {data.hex()}')
                    return
            except asyncio.TimeoutError:
                raise ConnectionError('Timed out writing request to stream.')
            except Exception as e:
                raise ConnectionError(f'SocketError while writing to stream: {e}')
        else:
            raise ConnectionError('Failed to instantiate stream.')
        

    async def read_from_stream(self, read_timeout_s: float = 15.0, max_response_size: int = 1024) -> bytes:
        """
        Reads bytes from ROC socket stream.

        Args:
            read_timeout_s (int, optional): Timeout in seconds to wait for read to complete. Defaults to 1.0
            max_response_size (int, optional): Maximum response size in bytes. Defaults to 1024.

        Raises:
            ConnectionError: Timed out waiting for read to complete, socket.error while reading, or stream_reader is null.

        Returns:
            bytes: Raw bytes read from stream.
        """
        self.logger.debug('Checking connection status.')
        await self.open_connection()
        if self._stream_reader:
            try:
                self.logger.debug('Reading data from stream...')
                async with asyncio.timeout(read_timeout_s):
                    response: bytes = await self._stream_reader.read(n=max_response_size)
                    self.logger.debug('Data read from stream successfully.')
                    self.logger.trace(f'Request: {response.hex()}')
                    return response
            except asyncio.TimeoutError:
                raise ConnectionError('Timed out reading response from stream.')
            except Exception as e:
                raise ConnectionError(f'Socket error while reading from stream: {e}')
        else:
            raise ConnectionError('Failed to instantiate stream.')