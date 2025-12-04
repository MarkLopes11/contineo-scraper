# 🎓 Contineo Portal Viewer

> A user-friendly Streamlit dashboard to view your Contineo student portal data without the hassle of logging in every time.

This project scrapes the Contineo student portal to provide a clean, fast, and insightful view of your academic data. Register once with your portal credentials, and then access your attendance and marks anytime using just a simple username.

## The Problem with the Official Portal

Logging into the official student portal can be tedious:
-   **Repetitive Login:** You have to enter your PRN and full Date of Birth every single time.
-   **Lack of Insights:** The portal shows your attendance percentage but doesn't tell you how many lectures you can afford to miss or need to attend to meet the 75% requirement.
-   **No Comparison:** There's no way to see how you're performing compared to your peers.

## ✨ Features

This dashboard solves these problems by providing:

-   **👤 One-Time Registration:** Securely save your PRN and DOB once, linked to a username of your choice.
-   **⚡️ Quick Data Fetching:** Just enter your username to instantly see your data.
-   **📊 Smart Attendance Tracker:**
    -   Displays your current attendance percentage for all subjects.
    -   **Calculates exactly how many lectures you can miss** while staying above 75% attendance.
    -   **Tells you how many lectures you must attend** to get back to 75% if you're below the threshold.
-   **📝 Detailed CIE Marks:** View a clean breakdown of your marks for MSE, ISE, and other exams.
-   **🏆 Semester Leaderboards:** See how you rank against your classmates.
-   **🔄 Live Data & Caching:**
    -   The "Fetch Data" button retrieves the data from the db making the process much faster.
    -   The "Get Live Data" button clears the cache and scrapes the portal for the most up-to-the-minute information.

## 📸 Demo

<img width="1820" height="825" alt="image" src="https://github.com/user-attachments/assets/5d9dedcf-e3e6-42f6-946a-b074009041e6" />


## 🛠️ Tech Stack

-   **Frontend:** [Streamlit](https://streamlit.io/)
-   **Web Scraping:** [Requests](https://requests.readthedocs.io/en/latest/) & [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
-   **Database:** [PostgreSQL](https://www.postgresql.org/)
-   **Deployment:** Streamlit Community Cloud

## 🚀 Local Setup and Installation

To run this project on your local machine, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/MarkLopes11/Contineo.git
    cd Contineo
    ```

2.  **Create a virtual environment and activate it:**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a file named `.env` in the root directory and add your PostgreSQL database connection string. You can get this from your database provider (like Neon, Supabase, or a local instance).

    `.env.example`:
    ```ini
    NEON_DB_PASSWORD=
    NEON_DB_URI=
    EMAIL_RECEIVER="reciever@gmail.com" # Where you want to receive the alerts
    RESEND_API_KEY= 
    ```
5. Configure the Application (`config.py`)

   The `config.py` file is the control panel for the scraper. You **must** update it for your Neon db url, name and user.
   ```ini
    PG_HOST = os.environ.get("NEON_DB_URI", "your actual url")
    PG_DBNAME = os.environ.get("PG_DBNAME", "db name")
    PG_USER = os.environ.get("PG_USER", "user name in the db")
    ```
  
6.  **Run the Streamlit app:**
    ```bash
    streamlit run st_main.py
    ```

## 📖 How to Use the App

1.  **Register:** Click on the "Register New Student" button in the sidebar. Fill in your details *exactly* as they appear on the student portal, along with a unique username you want to use.
2.  **Fetch Data:** Once registered, simply type your username in the "Enter your username" box and click "Fetch Data".
3.  **View:** Your attendance (with the 75% goal calculation) and CIE marks will be displayed. You can expand each subject to view marks and check the leaderboards for the semester rankings.
