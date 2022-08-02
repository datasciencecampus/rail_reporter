# https://stackoverflow.com/a/72346413

import yagmail


from_addr = "<source_address>"
to_addrs = ["<recipient_1>", "<recipient_2>"]
subject = "Testing email automation"
content = "This is the email body"
attachment_filepaths = ["outputs/any_file.csv"]
oauth2_file = "credentials.json"  # This is secret/protected

# Create connection object
yag = yagmail.SMTP(from_addr, oauth2_file=oauth2_file)

# Send
yag.send(
    to=to_addrs, subject=subject, contents=content, attachments=attachment_filepaths
)
