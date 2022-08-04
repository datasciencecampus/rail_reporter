import os
import yagmail
import logging

from datetime import datetime


def yag_send(
    from_addr: str,
    oauth2_file: str,
    to_addrs: list[str],
    subject: str,
    content: str,
    attachment_filepaths: list[str] = None,
) -> None:
    """
    Wraps yagmail for automatically emailing from within Python, including
    optional attachments.

    Arguments:
        from_addr -- "from" email address, used as login credential
        oauth2_file -- path to json file with Google-generated login creds
        to_addrs -- list of email addresses to send to, they will be visible to
        oneanother in the received emails!
        subject -- Email subject line
        content -- Main body of email (best stick to plaintext)
        attachment_filepaths -- list of filepaths to attachments to include

    Returns:
        None
    """

    # Create connection object
    yag = yagmail.SMTP(from_addr, oauth2_file=oauth2_file)

    # Send
    yag.send(
        to=to_addrs, subject=subject, contents=content, attachments=attachment_filepaths
    )
    return None


def email_rail_report(attachment_filepaths: list[str] = None) -> None:
    """
    Wraps process for reporting rail network statistics (specificity is due to
    environment variables loaded and messages created).

    Keyword Arguments:
        attachment_filepaths -- list of filepaths (str) to attach to the email
        (default: {None})

    Returns:
        None
    """
    logger = logging.getLogger(__name__)

    from_addr = os.getenv("RAIL_SEND_ADDR")
    to_addrs = os.getenv("RAIL_RECIPIENT").split("|")

    # Generate dated subject field
    subject = "Rail status report: {senddate}".format(
        senddate=str(datetime.now().date())
    )

    logger.info(f"To send: {subject}")
    logger.info(f"Attachments: {', '.join(attachment_filepaths)}")

    # Content is simple
    content = (
        "Please find attached latest rail network status statistics, "
        + "if you're seeing this the pipeline so far runs manually"
    )

    oauth2_file = "credentials.json"  # This is secret/protected

    yag_send(
        from_addr=from_addr,
        oauth2_file=oauth2_file,
        to_addrs=to_addrs,
        subject=subject,
        content=content,
        attachment_filepaths=attachment_filepaths,
    )

    logger.info("To process's knowledge, successfully sent")
    return None


if __name__ == "__main__":
    # Configure logging
    log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_fmt)
    logger = logging.getLogger(__name__)
    logger.info(
        "These functions are not meant to be executed standalone, "
        + "this will only send a test output to recipients."
    )

    # Send report with test file, if called standalone
    email_rail_report()
