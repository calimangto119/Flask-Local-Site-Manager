# Flask Site Manager

## Tags
#Python #Flask #PyQt5 #DesktopApp #WebDevelopment #Automation #SiteGenerator #GUI #LocalServer #Archiving #Windows

## Overview
**Flask Site Manager** is a modern PyQt5 desktop GUI application that enables developers and hobbyists to **create**, **run**, **archive**, and **restore** lightweight Flask web applications—locally and instantly.

This all-in-one management tool allows users to:
- Spin up new Flask projects with styled templates
- Launch and monitor local web servers
- Archive and restore project directories with ease
- Manage active and archived sites via a clean tabbed interface

Designed for Windows environments, it simplifies local Flask development and testing with minimal setup.

---

## 🚀 Features

- **One-Click Flask App Creation:** Auto-generates Flask projects with HTML/CSS, routing, and server scripts.
- **Port Management:** Automatically detects and assigns the next available port.
- **Visual Management Interface:** Tabbed UI to create, manage, or archive sites with live status updates.
- **Archiving/Restoration:** Zip and restore entire projects while maintaining metadata.
- **Browser Integration:** Instantly open sites in the browser from the GUI.
- **Atomic Operations:** Safer metadata writes and threaded background operations prevent freezing.

---

## 🛠️ Built With

- [Python 3.x](https://www.python.org/)
- [Flask](https://flask.palletsprojects.com/)
- [PyQt5](https://pypi.org/project/PyQt5/)
- [Waitress](https://docs.pylonsproject.org/projects/waitress/)
- [Windows OS Support](https://www.microsoft.com/windows)

---

## 🗂️ Directory Structure
📁 C:/PersonalSites/
├── site_name/
│ ├── app.py
│ ├── run_site.py
│ ├── static/css/style.css
│ └── templates/index.html
├── _archive/
│ └── site_name.zip
└── sites.json
