"""EDIT THIS FILE to change how every email is closed and signed.
(To change what the email SAYS and how it is structured, edit rules.md instead.)"""

CLOSING = "Best regards,"                 # line placed right before the signature
SIGN_TITLE = "Outreach Specialist"        # signature line 2
SIGN_COMPANY = "Level Up VFX"             # signature line 3
SIGN_COLOR = "#555555"                    # signature text colour
SIGN_FONT = "Poppins, Roboto, Montserrat, Arial, sans-serif"   # first font the reader's device has is used
SIGN_SIZE = "14px"
SEND_HTML = True                          # True = coloured/styled signature. False = plain text only.

# Words in a Gmail address that are NOT part of the person's name.
# vfx.chris.ewart@gmail.com -> "Chris Ewart"
NAME_IGNORE = {"vfx", "levelup", "level", "up", "outreach", "mail", "hello", "info", "team", "official", "gmail"}
