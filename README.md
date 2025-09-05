
# YudaiV3

[![YudaiV3 Logo](https://via.placeholder.com/300x100.png?text=YudaiV3+Logo)](https://yudai.app)



![NodeJS](https://img.shields.io/badge/node.js-6DA55F?style-for-the-badge&logo=node.js&logoColor=white)
![Vite](https://img.shields.io/badge/vite-%23646CFF.svg?style-for-the-badge&logo=vite&logoColor=white)
![GitHub](https://img.shields.io/badge/github-%23121011.svg?style-for-the-badge&logo=github&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-Python%20Linter-FF4500?style-for-the-badge&logo=python&logoColor=white)

## 
![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![TypeScript](https://img.shields.io/badge/typescript-%23007ACC.svg?style=for-the-badge&logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![GitHub Actions](https://img.shields.io/badge/github%20actions-%232671E5.svg?style=for-the-badge&logo=githubactions&logoColor=white)
![Ethereum](https://img.shields.io/badge/Ethereum-3C3C3D?style=for-the-badge&logo=Ethereum&logoColor=white)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Apache Spark](https://img.shields.io/badge/Apache%20Spark-FDEE21?style=flat-square&logo=apachespark&logoColor=black)
![Esbuild](https://img.shields.io/badge/esbuild-%23FFCF00.svg?style=for-the-badge&logo=esbuild&logoColor=black)
![PNPM](https://img.shields.io/badge/pnpm-%234a4a4a.svg?style=for-the-badge&logo=pnpm&logoColor=f69220)
![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
![TailwindCSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Vultr](https://img.shields.io/badge/Vultr-007BFC.svg?style=for-the-badge&logo=vultr)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Nginx](https://img.shields.io/badge/nginx-%23009639.svg?style=for-the-badge&logo=nginx&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-%23EE4C2C.svg?style=for-the-badge&logo=PyTorch&logoColor=white)

YudaiV3 is an **AI-powered coding agent** that connects to your GitHub repository to transform raw context—such as chat summaries, CSVs, PDFs, or plain text—into concise, actionable GitHub issues and pull requests. By leveraging file-dependency insights and analytics, YudaiV3 simplifies the development lifecycle, making it easier for teams to bridge the gap between ideas and implementation.

## 🎯 Who is YudaiV3 for?

YudaiV3 streamlines development workflows for a wide range of users:

- **Software Developers**: Generate feature scaffolds or bug fixes from high-level descriptions, reducing manual setup time.
- **Product Managers & Designers**: Convert user stories, mockups, or customer feedback into developer-ready GitHub issues without technical expertise.
- **Data Analysts & Scientists**: Transform data-driven insights (e.g., from CSVs or reports) into actionable engineering tasks.
- **Technical Teams**: Standardize and automate the creation of high-quality, bite-sized pull requests to improve collaboration and project management.

## ⚙️ Getting Started

Follow these steps to set up YudaiV3 locally or connect it to a hosted backend.

### Prerequisites
- **Node.js** (v16 or higher) and **pnpm** for the frontend.
- **Python** (v3.8 or higher) for the backend.
- **GitHub Account** with a repository to connect YudaiV3 to.
- A running backend (local or hosted) for API connectivity.

### 1. Clone the Repository
```bash
git clone https://github.com/pranay5255/YudaiV3.git
cd YudaiV3
```

### 2. Install Frontend Dependencies
```bash
pnpm install
```

### 3. Set Up GitHub App Authentication
YudaiV3 uses GitHub App OAuth for authentication. Follow these steps:

#### Create GitHub App
1. Go to [GitHub Settings → Developer settings → GitHub Apps](https://github.com/settings/apps)
2. Click "New GitHub App"
3. Configure your app:
   - **GitHub App name**: `YudaiV3` (or your preferred name)
   - **Homepage URL**: `http://localhost:3000` (for development)
   - **User authorization callback URL**: `http://localhost:3000/auth/callback`
4. Set permissions:
   - **Repository permissions**:
     - Contents: Read & Write
     - Issues: Read & Write
     - Pull requests: Read & Write
     - Metadata: Read
   - **User permissions**:
     - Email addresses: Read
     - Profile: Read
5. Generate a private key and download it

#### Configure Environment Variables
Create a `.env.dev` file in your project root:

```bash
# GitHub App OAuth Configuration (REQUIRED)
GITHUB_APP_CLIENT_ID=your_github_app_client_id
GITHUB_APP_CLIENT_SECRET=your_github_app_client_secret
GITHUB_APP_ID=your_github_app_numeric_id
GITHUB_APP_PRIVATE_KEY_PATH=/app/yudai-dev.2025-09-04.private-key.pem

# Frontend Configuration
FRONTEND_BASE_URL=http://localhost:3000
GITHUB_REDIRECT_URI=http://localhost:3000/auth/callback
VITE_API_BASE_URL=http://localhost:8001

# Database Configuration
DATABASE_URL=postgresql://yudai_user:yudai_password@db:5432/yudai_dev

# Other API Keys
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

#### Place Private Key
1. Download the private key from GitHub App settings
2. Place it at: `backend/yudai-dev.2025-09-04.private-key.pem`

### 4. Run the Development Server
```bash
pnpm run dev
```
The application will be available at `http://localhost:3000`.

### Backend Setup

The backend is containerized and can be deployed using Docker Compose. There are separate configurations for development and production:

#### Development Setup
```bash
# Start development environment
docker compose -f docker-compose-dev.yml up -d

# View logs
docker compose -f docker-compose-dev.yml logs -f

# Stop services
docker compose -f docker-compose-dev.yml down
```

#### Production Deployment

For production deployment, follow these steps:

1. **Create Production Environment Files**
   ```bash
   # Create .env.prod file with production settings
   cp .env.dev .env.prod
   # Edit .env.prod with production values
   ```

2. **SSL Certificate Setup**
   ```bash
   # Place SSL certificates in ssl/ directory
   # - ssl/fullchain.pem (certificate chain)
   # - ssl/privkey.pem (private key)
   ```

3. **GitHub App Production Setup**
   ```bash
   # Download production GitHub App private key
   # Place at: backend/yudaiv3.2025-08-02.private-key.pem

   # Update .env.prod with production GitHub App credentials:
   # GITHUB_APP_ID=your_production_app_id
   # GITHUB_APP_CLIENT_ID=your_production_client_id
   # GITHUB_APP_CLIENT_SECRET=your_production_client_secret
   ```

4. **Database Configuration**
   Update `.env.prod` with production PostgreSQL settings:
   ```bash
   POSTGRES_DB=yudai_prod
   POSTGRES_USER=your_prod_user
   POSTGRES_PASSWORD=your_secure_password
   DATABASE_URL=postgresql://your_prod_user:your_secure_password@db:5432/yudai_prod
   ```

5. **Deploy Production Services**
   ```bash
   # Start production environment
   docker compose -f docker-compose.prod.yml up -d

   # Check service health
   docker compose -f docker-compose.prod.yml ps

   # View logs
   docker compose -f docker-compose.prod.yml logs -f
   ```

6. **Production Configuration Changes**
   - **Resource Limits**: Production uses CPU/memory limits for stability
   - **Security**: Enhanced with Docker security options and no-new-privileges
   - **Logging**: Structured JSON logging with log rotation
   - **Health Checks**: Comprehensive health monitoring
   - **SSL/TLS**: HTTPS enabled with certificate management
   - **Database**: Optimized PostgreSQL configuration for production workloads

7. **Backup and Monitoring**
   ```bash
   # Database backups are automatically created in ./backups/postgres/
   # Logs are available in ./logs/

   # Monitor services
   docker compose -f docker-compose.prod.yml exec backend curl http://localhost:8000/health
   ```

8. **Scaling and Maintenance**
   ```bash
   # Update services
   docker compose -f docker-compose.prod.yml pull
   docker compose -f docker-compose.prod.yml up -d

   # Backup before updates
   docker compose -f docker-compose.prod.yml exec db pg_dump -U your_prod_user yudai_prod > backup.sql
   ```

**Security Notes:**
- Change all default passwords and secrets
- Use strong, unique credentials for database
- Keep GitHub App credentials secure
- Regularly update SSL certificates
- Monitor logs for security events

## 🛠️ Usage

Once YudaiV3 is running, you can feed it context to generate GitHub issues or pull requests:

1. **Provide Context**: Upload a file (e.g., CSV, PDF, or text) or input a chat summary via the web interface at `http://localhost:5173`.
2. **Generate Issues**: YudaiV3 analyzes the input and creates detailed GitHub issues with actionable tasks, including file dependencies and context.
3. **Create Pull Requests**: Based on the issues, YudaiV3 generates small, manageable pull requests with code suggestions or scaffolds.

**Example**:
- **Input**: A CSV with bug reports: `bug_id,description,priority,file`. E.g., `1,"Login button misaligned","High","src/components/Login.js"`.
- **Output**: A GitHub issue titled "Fix Login Button Misalignment" with a description, priority tag, and a reference to `src/components/Login.js`, followed by a pull request with suggested CSS fixes.

See the [documentation](#) (TBD) for detailed input formats and configuration options.

## 🤝 Contributing

We welcome contributions to YudaiV3! To get started:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Make your changes and commit (`git commit -m "Add your feature"`).
4. Push to your branch (`git push origin feature/your-feature`).
5. Open a pull request.

Please follow our [Code of Conduct](#) (TBD) and check the [issues page](https://github.com/pranay5255/YudaiV3/issues) for tasks to work on.

## 🚀 Roadmap

YudaiV3 is actively evolving. Planned features include:
- Support for additional input formats (e.g., JSON, Markdown).
- Enhanced AI-driven code suggestions for pull requests.
- Integration with other platforms like GitLab or Bitbucket.
- Comprehensive backend setup documentation.

Check the [issues page](https://github.com/pranay5255/YudaiV3/issues) for updates or to suggest features.

## 📜 License

YudaiV3 is an early-stage open-source project. The license is currently under consideration. Feel free to reach out via [issues](https://github.com/pranay5255/YudaiV3/issues) to discuss licensing preferences or usage terms.

## 📬 Contact

Have questions or feedback? Open an issue on [GitHub](https://github.com/pranay5255/YudaiV3/issues) or reach out to the team at [support@yudai.app](mailto:support@yudai.app).

Happy shipping! 🚢

---

© 2025 GitHub, Inc.
