from django.utils.translation import gettext_lazy as _


login_flex_content = {
  "type": "bubble",
  "body": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "text",
        "text": str(_('Account Binding')),
        "weight": "bold",
        "size": "xl"
      },
      {
        "type": "box",
        "layout": "vertical",
        "margin": "lg",
        "spacing": "sm",
        "contents": [
          {
            "type": "text",
            "text": str(_('Please go to the account binding page first'))
          }
        ]
      }
    ]
  },
  "footer": {
    "type": "box",
    "layout": "vertical",
    "spacing": "sm",
    "contents": [
      {
        "type": "button",
        "style": "link",
        "height": "sm",
        "action": {
          "type": "uri",
          "label": str(_('Account Binding')),
          "uri": "https://liff.line.me/1654867456-mZdEMWqg"
        }
      },
      {
        "type": "spacer"
      }
    ],
    "flex": 0
  }
}

login_flex_content_eng = {
  "type": "bubble",
  "body": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "text",
        "text": 'Account Binding',
        "weight": "bold",
        "size": "xl"
      },
      {
        "type": "box",
        "layout": "vertical",
        "margin": "lg",
        "spacing": "sm",
        "contents": [
          {
            "type": "text",
            "text": 'Please bind account first'
          }
        ]
      }
    ]
  },
  "footer": {
    "type": "box",
    "layout": "vertical",
    "spacing": "sm",
    "contents": [
      {
        "type": "button",
        "style": "link",
        "height": "sm",
        "action": {
          "type": "uri",
          "label": 'Account Binding',
          "uri": "https://liff.line.me/1654867456-V3NbvZ4Q"
        }
      },
      {
        "type": "spacer"
      }
    ],
    "flex": 0
  }
}