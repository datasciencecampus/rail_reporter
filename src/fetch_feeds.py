import os
import json
import click
import logging
import paramiko

from datetime import datetime


@click.command()
@click.argument("feed_type")
@click.argument("data_directory")
def main(feed_type: str, data_directory: str, latest_only=True):
    """
    Handles connecting to DTD SFTP rail data feed, and fetching latest, or all
    available.

    Arguments:
        feed_type -- Name of feed/directory to download from, on SFTP server
        data_directory -- Directory to save files to (must already exist)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Fetching {feed_type}")
    logger.info(os.getenv("RAIL_FEED_HOST"))

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

    if latest_only:
        # Filter to FULL data format only (rather than CHANGE format)
        remote_rail_files = [x for x in remote_rail_files if x[:5] == "RJTTF"]

        # Sort to id most recent data zip folder only
        remote_rail_files.sort()
        remote_rail_files = [remote_rail_files[-1]]

    # Check what files already exist
    logger.info("Checking for existing files")
    if not os.path.exists(os.getenv("DIR_DATA_EXTERNAL_ATOC")):
        os.makedirs(os.getenv("DIR_DATA_EXTERNAL_ATOC"))
    local_rail_files = [
        file
        for file in os.listdir(os.getenv("DIR_DATA_EXTERNAL_ATOC"))
        if file.endswith(".zip") | file.endswith(".ZIP")
    ]

    # download anything new
    to_download = set(remote_rail_files).difference(local_rail_files)

    if len(to_download) > 0:
        for file in to_download:
            sftp.get(
                os.path.join(f"./{feed_type}", file),
                os.path.join(data_directory, file),
            )
            logger.info(f"Retrieved {file}")
        logger.info(f"Retrieved {len(to_download)} files")

    # Shut down if left open
    if sftp:
        sftp.close()
    if transport:
        transport.close()

    # Return what happened
    if len(to_download) > 0:
        # Report via json
        with open("progress.json", "w") as f:
            json.dump({"new_files": True}, f)
        return True
    else:
        logger.info(f"No new rail data files in feed {feed_type} detected")
        with open("progress.json", "w") as f:
            json.dump({"new_files": False}, f)
        return False


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

    main()
