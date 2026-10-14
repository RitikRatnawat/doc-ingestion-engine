"""Module to verify the security constraints for the Webpages"""

import ipaddress
import socket
from urllib.parse import urlparse


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
            url_parts = urlparse(url)

            # Check for valid scheme
            if url_parts.scheme not in ("http", "https"):
                raise UnsafeURLError(f"Invalid URL scheme: {url_parts.scheme}")

            # Check for valid hostname
            if not url_parts.hostname:
                raise UnsafeURLError("URL must have a valid hostname.")

            # Resolve the hostname to an IP address
            ip_addr_info = socket.getaddrinfo(url_parts.hostname, url_parts.port or 443)

            for addr in ip_addr_info:
                ip_addr = ipaddress.ip_address(addr[4][0])

                # Check if the IP address is private, loopback, link-local, reserved, multicast, or unspecified
                if (
                    ip_addr.is_private
                    or ip_addr.is_loopback
                    or ip_addr.is_link_local
                    or ip_addr.is_reserved
                    or ip_addr.is_multicast
                    or ip_addr.is_unspecified
                ):
                    raise UnsafeURLError(f"Blocked IP address: {ip_addr}")

            return True

        except socket.gaierror as e:
            print(f"Socket error: {e}")
            return False

        except UnsafeURLError as e:
            print(f"Unsafe URL error: {e}")
            return False

        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
