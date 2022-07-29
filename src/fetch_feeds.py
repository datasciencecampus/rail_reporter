import os
import click
import logging
import paramiko


@click.command()
@click.argument("feed_type")
@click.argument("redo_all", type=click.BOOL, default=False)
def main(feed_type: str, redo_all: bool):
    """
    Handles connecting to DTD SFTP rail data feed, and fetching latest, or all
    available.

    Arguments:
        feed_type -- Name of feed to download, is name of directory on
        SFTP server
        redo_all -- flag, do you want to re-download all data available?
    """
    log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_fmt,
        filename=os.path.join(os.getenv("DIR_LOG"), "process.log"),
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Fetching {feed_type}, reprocess all = {redo_all}")

    paramiko.util.log_to_file(os.path.join(os.getenv("DIR_LOG"), "paramiko.log"))

    # Open a transport
    transport = paramiko.Transport(
        (os.getenv("RAIL_FEED_HOST"), os.getenv("RAIL_FEED_PORT"))
    )

    # Authorise
    transport.connect(None, os.getenv("RAIL_FEED_USER"), os.getenv("RAIL_FEED_PASS"))

    # Connect
    sftp = paramiko.SFTPClient.from_transport(transport)

    # Detect remote files available
    remote_rail_files = sftp.listdir(f"./{feed_type}")

    if redo_all:
        logger.info("Downloading every detected timetable file")
        # Download every file detected
        for file in remote_rail_files:
            sftp.get(
                os.path.join(f"./{feed_type}", file), os.getenv("DIR_DATA_EXTERNAL")
            )
        logger.info(f"Retrieved {len(remote_rail_files)} files")

    else:
        # Check what files already exist
        local_rail_files = [
            file
            for file in os.listdir(os.getenv("DIR_DATA_EXTERNAL"))
            if file.endswith(".zip")
        ]

        # download anything new
        to_download = set(remote_rail_files).difference(local_rail_files)
        if len(to_download) == 0:
            logger.info(f"No new rail data files in feed {feed_type} detected")
            return None

        for file in to_download:
            sftp.get(
                os.path.join(f"./{feed_type}", file), os.getenv("DIR_DATA_EXTERNAL")
            )

        logger.info(f"Retrieved {len(to_download)} files")

    return None

    # # Download
    # filepath = "/etc/passwd"
    # localpath = "test.zip"
    # sftp.get(filepath,localpath)

    # # Upload
    # filepath = "/home/foo.jpg"
    # localpath = "/home/pony.jpg"
    # sftp.put(localpath,filepath)

    # # Close
    # if sftp: sftp.close()
    # if transport: transport.close()
