"""Module to verify the security constraints for the Webpages"""

import ipaddress
import socket
from urllib.parse import urlparse

from .logger import logger


class UnsafeURLError(Exception):
    """Custom exception for URL validation errors."""

    pass


class URLValidator:
    """Class to validate URLs based on security constraints."""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validate the given URL against security constraints.

        Args:
            url (str): The URL to validate.

        Returns:
            bool: True if the URL is valid, False otherwise.

        Raises:
            UnsafeURLError: If the URL is invalid or violates security constraints.
        """

        try:
            logger.info(f"Checking the URL security and validating it for URL: {url}")
            url_parts = urlparse(url)
            logger.debug(f"Provided URL is parsed: {url_parts}")

            # Check for valid scheme
            logger.info("Validating the URL Scheme, should be either http or https")
            if url_parts.scheme not in ("http", "https"):
                raise UnsafeURLError(f"Invalid URL scheme: {url_parts.scheme}")
            logger.info(f"Successfully validated URL Scheme, Valid: {url_parts.scheme}")

            # Check for valid hostname
            logger.info("Validating the URL Host, should not be empty")
            if not url_parts.hostname:
                raise UnsafeURLError("URL must have a valid hostname.")
            logger.info(f"Successfully validated URL Host, Valid: {url_parts.hostname}")

            # Resolve the hostname to an IP address
            logger.info(f"Validating the Host {url_parts.hostname} is resolvable to IP Address or not")
            ip_addr_info = socket.getaddrinfo(url_parts.hostname, url_parts.port or 443)

            for addr in ip_addr_info:
                ip_addr = ipaddress.ip_address(addr[4][0])
                logger.debug(f"Checking for Host IP Address: {ip_addr}")

                # Check if the IP address is private, loopback, link-local, reserved, multicast, or unspecified
                logger.debug(
                    "Verifying that IP address should not be private, loopback, link-local, \
                    reserved, multicast, or unspecified"
                )
                if (
                    ip_addr.is_private
                    or ip_addr.is_loopback
                    or ip_addr.is_link_local
                    or ip_addr.is_reserved
                    or ip_addr.is_multicast
                    or ip_addr.is_unspecified
                ):
                    raise UnsafeURLError(f"Blocked IP address: {ip_addr}")

                logger.debug(f"Successfully verified that IP Address {ip_addr} is usable")

            logger.info(f"Succcessfully verified that Host {url_parts.hostname} is resolvable")
            return True

        except socket.gaierror as e:
            logger.error(f"Socket Error while resolving the URL Host: {e}")
            return False

        except UnsafeURLError as e:
            logger.error(f"Unsafe URL Error: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected Error while checking URL Safety: {e}")
            return False
