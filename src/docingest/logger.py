"""Module to add logging to the application"""

from __future__ import annotations

import logging


class Logger:
    _instance = None

    @staticmethod
    def get_instance(
        name: str = "docingest", level: int = logging.DEBUG, logging_file: str = "app.log"
    ) -> logging.Logger:
        """Static Method to get logger instance

        Args:
            name (str, optional): Name of the logger. Defaults to "docingest".
            level (int, optional): Logging level. Defaults to logging.INFO.
            logging_file (str, optional): Path to the logging file. Defaults to "app.log".

        Returns:
            logging.Logger: Logger instance
        """

        if Logger._instance is None:
            Logger._instance = Logger(name, level, logging_file)

        return Logger._instance

    def __init__(self, name: str, level: int, logging_file: str) -> None:
        """Initialize the Logger instance

        Args:
            name (str): Name of the logger
            level (int): Logging level
            logging_file (str): Path to the logging file
        """

        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if not self.logger.handlers:
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

            # Create a file handler
            file_handler = logging.FileHandler(logging_file)
            file_handler.setFormatter(formatter)

            # Create a console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)

            # Adding handlers to the logger
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            self.logger.propagate = False

    def debug(self, message: str) -> None:
        """Log a debug message

        Args:
            message (str): Message to log
        """

        self.logger.debug(message)

    def info(self, message: str) -> None:
        """Log an info message

        Args:
            message (str): Message to log
        """

        self.logger.info(message)

    def warning(self, message: str) -> None:
        """Log a warning message

        Args:
            message (str): Message to log
        """

        self.logger.warning(message)

    def error(self, message: str) -> None:
        """Log an error message

        Args:
            message (str): Message to log
        """

        self.logger.error(message)

    def critical(self, message: str) -> None:
        """Log a critical message

        Args:
            message (str): Message to log
        """

        self.logger.critical(message)


logger = Logger.get_instance()
