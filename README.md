# GPBus API

<p align="center" style="margin: 0; padding: 0;">
  <img src="readme_images/gpbus_logo.png" alt="gpbus_logo" width="200">
</p>

## Description
This is an gateway api for the two mobile apps in the repository [gpbus mobile](https://github.com/newtonepv/gpbus_mobile).
This api intermediates the communication between these apps and the GPBus postgreSQL database.

<hr>

## Contents
- [Features](#features)
- [Installing & hosting](#installing-and-running)

<hr>


## Features
- Limiting database connections per ip adress.
- Limiting total database connections.
- Solving some concurrency problems.

<hr>

## Pending Features
- Improving security.

<hr>

## Hosting steps
### Prerequisites
Check the [python_requisites.txt](#https://github.com/newtonepv/gpbus_api/blob/main/python_requirements.txt) file

### Hosting Steps
- Clone the repository:
  ```bash
  git clone https://github.com/newtonepv/gpbus_api.git
  cd gpbus_api
  ```
- Create the .env file:
  ```bash
  cat > .env <<< "DATABASE_URL=your_database_url_here"
  ```
  Ensure you replaced the <b>"insert_your_url_here"</b> with you real neondb connection string.
- Run your api
  ```bash
  python main.py
  ```
After following thoose steps, your api should already be running at: <b>http://0.0.0.0:8000</b>
