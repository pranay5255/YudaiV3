
# YudaiV3

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
![TypeScript](https://img.shields.io/badge/typescript-%23007ACC.svg?style=for-the-badge&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/vite-%23646CFF.svg?style=for-the-badge&logo=vite&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white)

YudaiV3 is an **AI-powered coding agent** that connects to your GitHub repository to transform raw context—such as chat summaries, CSVs, PDFs, or plain text—into concise, actionable GitHub issues and pull requests. By leveraging file-dependency insights and analytics, YudaiV3 simplifies the development lifecycle, making it easier for teams to bridge the gap between ideas and implementation.

## 🎯 Who is YudaiV3 for?

YudaiV3 streamlines development workflows for a wide range of users:

- **Software Developers**: Generate feature scaffolds or bug fixes from high-level descriptions, reducing manual setup time.
- **Product Managers & Designers**: Convert user stories, mockups, or customer feedback into developer-ready GitHub issues without technical expertise.
- **Technical Teams**: Standardize and automate the creation of high-quality, bite-sized pull requests to improve collaboration and project management.

## ✨ Core Features

- **Context-Rich Issue Generation**: Turns unstructured data (CSVs, notes, PDFs) into detailed, actionable GitHub issues.
- **Three-Agent Architecture**: A specialized pipeline of PM, Architect, and Coder agents ensures a seamless flow from raw data to test-driven code.
- **Automated Workflow**: From data analysis to PR creation, Yudai automates the tedious parts of project management and development.
- **Local & Cloud Ready**: Run it on your own infrastructure for privacy or use our cloud version for convenience.

![YudaiV3 Architecture](arch.png)

## ⚙️ Getting Started

Follow these steps to set up YudaiV3 locally.

### Prerequisites
- **Node.js** (v16 or higher)
- **Python** (v3.8 or higher)
- **GitHub Account** with a repository to connect YudaiV3 to.

### 1. Clone the Repository
```bash
git clone https://github.com/pranay5255/YudaiV3.git
cd YudaiV3
```

### 2. Install Frontend Dependencies
The frontend is a React/Vite application.
```bash
npm install # or pnpm install / yarn install
```

### 3. Set Up the Backend
The backend is a Python application using FastAPI.
```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

### 4. Run the Development Servers
- **Run the frontend:**
```bash
# From the root directory
npm run dev
```
The application will be available at `http://localhost:5173`.

- **Run the backend:**
```bash
# From the backend directory
uvicorn main:app --reload
```
The API will be running on `http://localhost:8000`.

## 🚀 Roadmap & Upcoming Releases

YudaiV3 is actively evolving. Here are some of the exciting features planned:

- **Data Agent Integration**: Upcoming releases will introduce specialized **Data Analyst and Data Scientist agents**. These agents will allow you to perform complex data analysis, generate insights, and automatically create engineering tasks based on your findings.
- **Enhanced AI-driven code suggestions**: Improving the Coder agent to provide more accurate and context-aware code.
- **Expanded Integrations**: Support for other platforms like GitLab, Bitbucket, and Jira.
- **Advanced Data Handling**: Support for more input formats like JSON, Markdown, and direct database connections.

Check the [issues page](https://github.com/pranay5255/YudaiV3/issues) for updates or to suggest features.

## 🤝 Contributing

We welcome contributions to YudaiV3! To get started:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Make your changes and commit (`git commit -m "Add your feature"`).
4. Push to your branch (`git push origin feature/your-feature`).
5. Open a pull request.

Please check the [issues page](https://github.com/pranay5255/YudaiV3/issues) for tasks to work on.

## 📜 License

YudaiV3 is an early-stage open-source project. The license is currently TBD.

---

**Happy shipping!** 🚢
