import os
import click
import logging
import paramiko

from datetime import datetime


@click.command()
@click.argument("feed_type")
def fetch_feeds(feed_type: str):
    """
    Handles connecting to DTD SFTP rail data feed, and fetching latest, or all
    available.

    Arguments:
        feed_type -- Name of feed/directory to download from, on SFTP server
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Fetching {feed_type}")

    # Open a transport
    transport = paramiko.Transport(
        (os.getenv("RAIL_FEED_HOST"), int(os.getenv("RAIL_FEED_PORT")))
    )

    # Authorise
    transport.connect(None, os.getenv("RAIL_FEED_USER"), os.getenv("RAIL_FEED_PASS"))

    # Connect
    sftp = paramiko.SFTPClient.from_transport(transport)

    # Detect remote files available
    remote_rail_files = sftp.listdir(f"./{feed_type}")

    # Check what files already exist
    logger.info("Checking for existing files")
    local_rail_files = [
        file
        for file in os.listdir(os.getenv("DIR_DATA_EXTERNAL_ATOC"))
        if file.endswith(".zip")
    ]

    # download anything new
    to_download = set(remote_rail_files).difference(local_rail_files)
    if len(to_download) > 0:
        for file in to_download:
            sftp.get(
                os.path.join(f"./{feed_type}", file),
                os.path.join(os.getenv("DIR_DATA_EXTERNAL_ATOC"), file),
            )
            logger.info(f"Retrieved {file}")
        logger.info(f"Retrieved {len(to_download)} files")
    else:
        logger.info(f"No new rail data files in feed {feed_type} detected")

    # Shut down if left open
    if sftp:
        sftp.close()
    if transport:
        transport.close()

    return None


if __name__ == "__main__":
    # Configure logging
    log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_fmt,
        filename=os.path.join(
            os.getenv("DIR_LOG"), f"{str(datetime.now().date())}.log"
        ),
    )

    fetch_feeds()
