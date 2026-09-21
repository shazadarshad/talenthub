"""
Seed script: creates 20 realistic candidate accounts + profiles, each with
a genuine text-based CV PDF (real generated content, not placeholder text).

Safe to run multiple times: skips any candidate whose email already exists.

Run locally:   python seed_candidates.py
Run on Railway: railway run --service talenthub python seed_candidates.py
"""
import io
import sys

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from app import create_app
from app.extensions import db
from app.models import User, CandidateProfile

# ---------------------------------------------------------------------
# 20 candidate personas: varied roles, experience levels, locations,
# skills, and realistic CV content (summary, experience, education).
# ---------------------------------------------------------------------
CANDIDATES = [
    {
        "full_name": "Amara Wickramasinghe", "email": "amara.wickramasinghe@example.com",
        "role_wanted": "Frontend Developer", "location": "Colombo, Sri Lanka",
        "experience_level": "Entry",
        "skills": "HTML, CSS, JavaScript, React, Git",
        "cover_letter": (
            "I'm a recent computer science graduate passionate about building clean, "
            "accessible user interfaces. During my degree I built several React projects "
            "and contributed to a university open-source club. I'm looking for my first "
            "full-time role where I can keep learning modern frontend practices."
        ),
        "cv": {
            "summary": "Recent Computer Science graduate with hands-on React project experience.",
            "experience": [
                "Freelance Web Developer, 2024-Present - Built 3 small business websites using React and Tailwind CSS.",
                "University Open Source Club, 2023-2024 - Contributed UI fixes to a student-run scheduling app.",
            ],
            "education": "BSc (Hons) Computer Science, University of Colombo, 2024",
            "extra_skills": "Responsive design, basic Figma, Agile fundamentals",
        },
    },
    {
        "full_name": "Nadeesha Perera", "email": "nadeesha.perera@example.com",
        "role_wanted": "Backend Developer", "location": "Kandy, Sri Lanka",
        "experience_level": "Junior",
        "skills": "Python, Flask, PostgreSQL, Docker, REST APIs",
        "cover_letter": (
            "I've spent the last year and a half building backend services for a fintech "
            "startup, mainly REST APIs in Flask with PostgreSQL. I enjoy writing clean, "
            "well-tested code and I'm particularly interested in scaling systems that "
            "handle real transaction volume."
        ),
        "cv": {
            "summary": "Backend developer with 1.5 years building production Flask APIs for a fintech startup.",
            "experience": [
                "Backend Developer, PayWave Technologies, 2023-Present - Built and maintained REST APIs handling 50,000+ daily transactions.",
                "Intern Developer, PayWave Technologies, 2023 - Assisted with database migrations and API testing.",
            ],
            "education": "BSc Software Engineering, SLIIT, 2023",
            "extra_skills": "SQLAlchemy, pytest, basic AWS (EC2, S3), CI/CD with GitHub Actions",
        },
    },
    {
        "full_name": "Ruwan Fernando", "email": "ruwan.fernando@example.com",
        "role_wanted": "Full-Stack Developer", "location": "Galle, Sri Lanka",
        "experience_level": "Mid",
        "skills": "JavaScript, Node.js, React, MongoDB, Express, TypeScript",
        "cover_letter": (
            "Over the past 4 years I've built and shipped full-stack web applications end "
            "to end, from database schema design to polished frontend UI. I led the rebuild "
            "of a logistics tracking platform that's now used daily by over 200 drivers. "
            "I'm looking for a role with more ownership over architecture decisions."
        ),
        "cv": {
            "summary": "Full-stack developer with 4 years of experience across the MERN stack, including leading a platform rebuild.",
            "experience": [
                "Senior Software Engineer, RouteLogic Pvt Ltd, 2022-Present - Led rebuild of logistics tracking platform (React + Node.js + MongoDB), used by 200+ drivers daily.",
                "Software Engineer, RouteLogic Pvt Ltd, 2021-2022 - Built customer-facing dashboard features and REST APIs.",
                "Junior Developer, CodeSpring Labs, 2020-2021 - Maintained internal tools in JavaScript and PHP.",
            ],
            "education": "BSc Information Technology, University of Moratuwa, 2020",
            "extra_skills": "TypeScript, Redis, WebSockets, basic Kubernetes, mentoring junior developers",
        },
    },
    {
        "full_name": "Dilani Rajapaksa", "email": "dilani.rajapaksa@example.com",
        "role_wanted": "Data Analyst", "location": "Colombo, Sri Lanka",
        "experience_level": "Junior",
        "skills": "SQL, Python, Excel, Power BI, Data Visualization",
        "cover_letter": (
            "I love turning messy data into clear insights that actually change decisions. "
            "In my current role I built weekly sales dashboards that the leadership team now "
            "checks every Monday. I'm looking to grow into a role with more statistical "
            "modeling and less manual reporting."
        ),
        "cv": {
            "summary": "Data analyst with 2 years of experience building dashboards and sales reporting pipelines.",
            "experience": [
                "Data Analyst, Ceylon Retail Group, 2023-Present - Built Power BI dashboards tracking sales across 40 stores, used weekly by leadership.",
                "Junior Data Analyst, Ceylon Retail Group, 2022-2023 - Automated monthly reporting, cutting manual work from 2 days to 2 hours.",
            ],
            "education": "BSc Statistics, University of Kelaniya, 2022",
            "extra_skills": "pandas, basic machine learning, A/B testing fundamentals",
        },
    },
    {
        "full_name": "Kasun Bandara", "email": "kasun.bandara@example.com",
        "role_wanted": "DevOps Engineer", "location": "Remote",
        "experience_level": "Senior",
        "skills": "AWS, Kubernetes, Terraform, Docker, CI/CD, Linux",
        "cover_letter": (
            "I've spent the last 7 years building and operating infrastructure for "
            "high-availability systems. I led the migration of a monolith to Kubernetes "
            "microservices, reducing deployment time from 45 minutes to under 5. I care "
            "deeply about reliability, observability, and making on-call less painful."
        ),
        "cv": {
            "summary": "Senior DevOps engineer with 7 years of experience leading cloud infrastructure and Kubernetes migrations.",
            "experience": [
                "Senior DevOps Engineer, CloudNine Systems, 2020-Present - Led migration from monolith to Kubernetes microservices, cutting deploy time from 45 to 5 minutes.",
                "DevOps Engineer, CloudNine Systems, 2018-2020 - Built Terraform infrastructure-as-code for AWS, managing 30+ environments.",
                "Systems Administrator, NetSolve Lanka, 2016-2018 - Managed on-prem Linux servers and backup systems.",
            ],
            "education": "BSc Computer Engineering, University of Peradeniya, 2016",
            "extra_skills": "Prometheus, Grafana, Helm, incident response, cost optimization (reduced AWS bill by 30%)",
        },
    },
    {
        "full_name": "Tharushi Silva", "email": "tharushi.silva@example.com",
        "role_wanted": "QA Engineer", "location": "Negombo, Sri Lanka",
        "experience_level": "Entry",
        "skills": "Manual Testing, Selenium, Test Case Design, Jira",
        "cover_letter": (
            "I completed an intensive QA bootcamp and have since been testing a mobile "
            "banking app as part of a contract role, focusing on manual and basic automated "
            "regression testing. I'm meticulous about edge cases and enjoy the detective "
            "work of finding bugs before customers do."
        ),
        "cv": {
            "summary": "Entry-level QA engineer with contract experience testing a mobile banking application.",
            "experience": [
                "QA Tester (Contract), FinSecure Mobile, 2024-Present - Manual and regression testing for a mobile banking app, logged 150+ verified bugs.",
                "QA Bootcamp Graduate, TestPro Academy, 2024 - Completed 3-month intensive course covering manual and Selenium-based automated testing.",
            ],
            "education": "Diploma in Software Quality Assurance, TestPro Academy, 2024",
            "extra_skills": "Basic Selenium WebDriver, Postman for API testing, bug tracking in Jira",
        },
    },
    {
        "full_name": "Chamara Wijesinghe", "email": "chamara.wijesinghe@example.com",
        "role_wanted": "Mobile Developer (Android)", "location": "Colombo, Sri Lanka",
        "experience_level": "Mid",
        "skills": "Kotlin, Java, Android SDK, Jetpack Compose, Firebase",
        "cover_letter": (
            "I've published two apps on the Play Store, one of which has over 50,000 "
            "downloads. I specialize in Kotlin and Jetpack Compose, and I'm comfortable "
            "owning a feature from design handoff through release. I'm looking for a team "
            "building something people actually use daily."
        ),
        "cv": {
            "summary": "Android developer with 3 years of experience, including two published apps with over 50,000 combined downloads.",
            "experience": [
                "Android Developer, AppForge Studios, 2022-Present - Built and shipped a fitness tracking app with 50,000+ downloads using Kotlin and Jetpack Compose.",
                "Junior Android Developer, AppForge Studios, 2021-2022 - Maintained legacy Java codebase, migrated key screens to Kotlin.",
            ],
            "education": "BSc Computer Science, NSBM Green University, 2021",
            "extra_skills": "Firebase (Auth, Firestore, Analytics), MVVM architecture, Play Store release management",
        },
    },
    {
        "full_name": "Ishara Gunawardena", "email": "ishara.gunawardena@example.com",
        "role_wanted": "UI/UX Designer", "location": "Colombo, Sri Lanka",
        "experience_level": "Junior",
        "skills": "Figma, User Research, Wireframing, Prototyping, Adobe XD",
        "cover_letter": (
            "I redesigned the onboarding flow for a food delivery app that increased "
            "completion rate by 18%, backed by user interviews and A/B testing. I care "
            "about design decisions being grounded in real user feedback, not just "
            "aesthetics."
        ),
        "cv": {
            "summary": "UI/UX designer with 2 years of experience, notably improving an onboarding flow's completion rate by 18%.",
            "experience": [
                "UI/UX Designer, QuickBite App, 2023-Present - Redesigned onboarding flow, increasing completion rate by 18% via user research and A/B testing.",
                "Junior Designer, Pixel & Co Studio, 2022-2023 - Created wireframes and prototypes for client web projects.",
            ],
            "education": "BA Design, Academy of Design, 2022",
            "extra_skills": "Usability testing, design systems, basic HTML/CSS for handoff",
        },
    },
    {
        "full_name": "Malith Karunaratne", "email": "malith.karunaratne@example.com",
        "role_wanted": "Machine Learning Engineer", "location": "Colombo, Sri Lanka",
        "experience_level": "Mid",
        "skills": "Python, TensorFlow, PyTorch, scikit-learn, NLP",
        "cover_letter": (
            "I built a customer churn prediction model that's now used by our sales team "
            "to prioritize retention calls, improving retention by 12%. Most of my work "
            "has been in NLP, including a support-ticket classification system that "
            "reduced manual triage time significantly."
        ),
        "cv": {
            "summary": "ML engineer with 3.5 years of experience, including production churn prediction and NLP classification systems.",
            "experience": [
                "Machine Learning Engineer, DataSphere Analytics, 2022-Present - Built churn prediction model improving customer retention by 12%; built NLP ticket classifier cutting triage time by 60%.",
                "Data Scientist, DataSphere Analytics, 2021-2022 - Built exploratory models and dashboards for internal stakeholders.",
            ],
            "education": "MSc Data Science, University of Colombo School of Computing, 2021",
            "extra_skills": "Hugging Face Transformers, MLflow, model deployment with Docker + FastAPI",
        },
    },
    {
        "full_name": "Sanduni Herath", "email": "sanduni.herath@example.com",
        "role_wanted": "Product Manager", "location": "Colombo, Sri Lanka",
        "experience_level": "Senior",
        "skills": "Product Strategy, Roadmapping, User Research, Agile, SQL",
        "cover_letter": (
            "I've led product for a B2B SaaS platform through 4x revenue growth over 3 "
            "years, working closely with engineering, design, and sales to prioritize the "
            "roadmap. I'm data-driven but never lose sight of the actual user problem "
            "we're solving."
        ),
        "cv": {
            "summary": "Senior product manager with 6 years of experience, leading a B2B SaaS product through 4x revenue growth.",
            "experience": [
                "Senior Product Manager, Vantage B2B Solutions, 2021-Present - Led product roadmap through 4x revenue growth over 3 years; shipped 25+ major features.",
                "Product Manager, Vantage B2B Solutions, 2019-2021 - Owned onboarding and billing product areas.",
                "Business Analyst, Colombo Insurance Group, 2017-2019 - Gathered requirements and wrote specs for internal tools.",
            ],
            "education": "MBA, Postgraduate Institute of Management, 2017",
            "extra_skills": "Stakeholder management, pricing strategy, competitive analysis, SQL for self-serve analytics",
        },
    },
    {
        "full_name": "Yohan De Silva", "email": "yohan.desilva@example.com",
        "role_wanted": "Cloud Engineer", "location": "Remote",
        "experience_level": "Mid",
        "skills": "AWS, Azure, Terraform, Python, Networking",
        "cover_letter": (
            "I design and manage multi-cloud infrastructure for clients across retail and "
            "healthcare. Recently I led a cost-optimization project that cut a client's "
            "monthly AWS bill by 35% without any performance tradeoff. I enjoy the puzzle "
            "of balancing cost, performance, and security."
        ),
        "cv": {
            "summary": "Cloud engineer with 4 years of AWS/Azure experience, including a 35% cloud cost reduction project.",
            "experience": [
                "Cloud Engineer, NimbusWorks Consulting, 2022-Present - Led cost-optimization project cutting a client's AWS bill by 35%; manage infrastructure for 6 enterprise clients.",
                "Junior Cloud Engineer, NimbusWorks Consulting, 2021-2022 - Built Terraform modules for repeatable client deployments.",
            ],
            "education": "BSc Information Systems, University of Sri Jayewardenepura, 2021",
            "extra_skills": "AWS Certified Solutions Architect, VPC design, cost monitoring dashboards",
        },
    },
    {
        "full_name": "Piumi Jayasuriya", "email": "piumi.jayasuriya@example.com",
        "role_wanted": "Cybersecurity Analyst", "location": "Colombo, Sri Lanka",
        "experience_level": "Junior",
        "skills": "Network Security, SIEM, Incident Response, Python",
        "cover_letter": (
            "I monitor and respond to security alerts for a mid-size fintech company, and "
            "last year I identified a phishing campaign before it compromised any accounts. "
            "I'm working toward my Security+ certification and want to move deeper into "
            "threat hunting."
        ),
        "cv": {
            "summary": "Security analyst with 2 years of SOC experience, including catching a phishing campaign before it caused damage.",
            "experience": [
                "SOC Analyst, SecureBank Technologies, 2023-Present - Monitor SIEM alerts, identified and contained a phishing campaign before account compromise.",
                "IT Support Technician, SecureBank Technologies, 2022-2023 - Handled internal helpdesk tickets and access management.",
            ],
            "education": "BSc Cybersecurity, Informatics Institute of Technology, 2022",
            "extra_skills": "Splunk, basic penetration testing, CompTIA Security+ (in progress)",
        },
    },
    {
        "full_name": "Lakshan Abeywardena", "email": "lakshan.abeywardena@example.com",
        "role_wanted": "Database Administrator", "location": "Kurunegala, Sri Lanka",
        "experience_level": "Mid",
        "skills": "PostgreSQL, MySQL, Database Tuning, Backup & Recovery, SQL",
        "cover_letter": (
            "I manage database infrastructure for an e-commerce platform processing over "
            "10,000 orders a day. I led a query optimization project that cut average "
            "response time by 70% during peak sales events, and I take backup integrity "
            "very seriously after seeing what happens when it's neglected."
        ),
        "cv": {
            "summary": "Database administrator with 4 years of experience managing high-traffic e-commerce database infrastructure.",
            "experience": [
                "Database Administrator, ShopWave Lanka, 2021-Present - Led query optimization cutting peak response time by 70%; manage backup/recovery for 10,000+ daily orders.",
                "Junior DBA, ShopWave Lanka, 2020-2021 - Assisted with database migrations and monitoring.",
            ],
            "education": "BSc Computer Science, Wayamba University, 2020",
            "extra_skills": "Index tuning, replication setup, disaster recovery planning",
        },
    },
    {
        "full_name": "Nimesha Rathnayake", "email": "nimesha.rathnayake@example.com",
        "role_wanted": "Site Reliability Engineer", "location": "Remote",
        "experience_level": "Senior",
        "skills": "Kubernetes, Prometheus, Go, Python, Incident Management",
        "cover_letter": (
            "I've spent 6 years keeping distributed systems online, most recently leading "
            "the on-call rotation for a platform serving 2 million monthly active users. "
            "I built our current alerting system from scratch after realizing our old one "
            "was causing more alert fatigue than it prevented outages."
        ),
        "cv": {
            "summary": "Senior SRE with 6 years of experience, leading reliability efforts for a platform with 2 million monthly active users.",
            "experience": [
                "Senior Site Reliability Engineer, StreamCast Media, 2021-Present - Rebuilt alerting system, reducing false-positive pages by 80%; lead on-call rotation for 2M MAU platform.",
                "SRE, StreamCast Media, 2019-2021 - Built Kubernetes-based deployment pipelines and monitoring dashboards.",
                "Backend Engineer, StreamCast Media, 2017-2019 - Built core video streaming APIs.",
            ],
            "education": "BSc Computer Engineering, University of Moratuwa, 2017",
            "extra_skills": "Chaos engineering, capacity planning, postmortem culture, Go microservices",
        },
    },
    {
        "full_name": "Oshadha Liyanage", "email": "oshadha.liyanage@example.com",
        "role_wanted": "Business Analyst", "location": "Colombo, Sri Lanka",
        "experience_level": "Entry",
        "skills": "Requirements Gathering, SQL, Excel, Process Mapping, Stakeholder Communication",
        "cover_letter": (
            "I recently completed my degree in Business Information Systems and did a "
            "6-month internship where I documented requirements for a warehouse management "
            "system rollout. I enjoy bridging the gap between what business teams need and "
            "what engineers can actually build."
        ),
        "cv": {
            "summary": "Entry-level business analyst with internship experience documenting requirements for a warehouse management rollout.",
            "experience": [
                "Business Analyst Intern, Logix Warehouse Solutions, 2024 - Documented requirements and process maps for a warehouse management system rollout across 3 sites.",
            ],
            "education": "BSc Business Information Systems, University of Sri Jayewardenepura, 2024",
            "extra_skills": "BPMN process mapping, basic SQL querying, user story writing",
        },
    },
    {
        "full_name": "Hasitha Mendis", "email": "hasitha.mendis@example.com",
        "role_wanted": "Game Developer", "location": "Colombo, Sri Lanka",
        "experience_level": "Junior",
        "skills": "Unity, C#, Game Design, 3D Modeling Basics",
        "cover_letter": (
            "I shipped a mobile puzzle game that reached #12 in the local app store puzzle "
            "category, built solo in Unity over 8 months. I handle everything from gameplay "
            "programming to basic art integration, and I'm hungry to join a team working on "
            "something bigger than what I can build alone."
        ),
        "cv": {
            "summary": "Junior game developer who independently shipped a mobile puzzle game that reached #12 in its local app store category.",
            "experience": [
                "Indie Game Developer (Solo), 2023-Present - Built and published a mobile puzzle game in Unity, reaching #12 in local puzzle category rankings.",
                "Game Design Intern, PixelForge Studio, 2022 - Assisted with level design and playtesting for a 2D platformer.",
            ],
            "education": "BSc Game Development, ICBT Campus, 2023",
            "extra_skills": "Unity Animator, basic shaders, mobile monetization (ads/IAP)",
        },
    },
    {
        "full_name": "Anjalie Wanniarachchi", "email": "anjalie.wanniarachchi@example.com",
        "role_wanted": "Technical Writer", "location": "Remote",
        "experience_level": "Mid",
        "skills": "API Documentation, Markdown, Technical Editing, Developer Tools",
        "cover_letter": (
            "I've written and maintained API documentation for a developer platform used "
            "by over 5,000 external developers, and I led a documentation overhaul that "
            "cut support tickets about integration issues by 40%. I care about writing "
            "that developers can actually use without pinging support."
        ),
        "cv": {
            "summary": "Technical writer with 4 years of experience, notably reducing integration support tickets by 40% through documentation improvements.",
            "experience": [
                "Senior Technical Writer, DevPlatform API Co, 2022-Present - Led documentation overhaul, reducing integration-related support tickets by 40%; docs used by 5,000+ external developers.",
                "Technical Writer, DevPlatform API Co, 2020-2022 - Wrote and maintained REST API reference docs and tutorials.",
            ],
            "education": "BA English & Communication, University of Kelaniya, 2020",
            "extra_skills": "Docs-as-code workflows, OpenAPI/Swagger, basic Python for code samples",
        },
    },
    {
        "full_name": "Dinesh Ekanayake", "email": "dinesh.ekanayake@example.com",
        "role_wanted": "Embedded Systems Engineer", "location": "Kandy, Sri Lanka",
        "experience_level": "Mid",
        "skills": "C, C++, Embedded Linux, ARM Microcontrollers, RTOS",
        "cover_letter": (
            "I design firmware for IoT sensor devices deployed in agricultural monitoring "
            "systems across several tea estates. I led the migration of our firmware to a "
            "real-time OS, improving sensor reading reliability significantly in the field. "
            "I enjoy the constraints of embedded work - every byte and every millisecond "
            "counts."
        ),
        "cv": {
            "summary": "Embedded systems engineer with 3 years of experience building firmware for IoT agricultural sensors.",
            "experience": [
                "Embedded Systems Engineer, AgriSense IoT, 2022-Present - Led firmware migration to RTOS, improving field sensor reliability; devices deployed across 15 tea estates.",
                "Junior Firmware Engineer, AgriSense IoT, 2021-2022 - Wrote low-level drivers for sensor communication over I2C/SPI.",
            ],
            "education": "BSc Electronic & Telecommunication Engineering, University of Moratuwa, 2021",
            "extra_skills": "FreeRTOS, low-power design, I2C/SPI/UART protocols, basic PCB reading",
        },
    },
    {
        "full_name": "Sachini Amarasinghe", "email": "sachini.amarasinghe@example.com",
        "role_wanted": "IT Support Specialist", "location": "Matara, Sri Lanka",
        "experience_level": "Entry",
        "skills": "Windows Administration, Networking Basics, Helpdesk, Troubleshooting",
        "cover_letter": (
            "I completed my diploma in IT support and have been handling helpdesk tickets "
            "for a local school district, resolving issues for over 200 staff computers "
            "and the school network. I'm patient, methodical, and genuinely enjoy helping "
            "people who are frustrated with technology feel unstuck."
        ),
        "cv": {
            "summary": "Entry-level IT support specialist currently managing helpdesk operations for a school district's IT infrastructure.",
            "experience": [
                "IT Support Technician, Southern Province Education Office, 2024-Present - Resolve helpdesk tickets for 200+ staff computers and manage basic network troubleshooting.",
            ],
            "education": "Diploma in Information Technology, Matara Technical College, 2024",
            "extra_skills": "Active Directory basics, printer/network troubleshooting, Microsoft 365 administration",
        },
    },
    {
        "full_name": "Buddhika Senanayake", "email": "buddhika.senanayake@example.com",
        "role_wanted": "Backend Developer", "location": "Anuradhapura, Sri Lanka",
        "experience_level": "Senior",
        "skills": "Java, Spring Boot, Microservices, Kafka, PostgreSQL",
        "cover_letter": (
            "I've architected and led development of microservices systems for a payments "
            "platform processing millions of dollars monthly. I mentor a team of 4 junior "
            "developers and I'm the person people come to when a production incident needs "
            "calm, methodical debugging under pressure."
        ),
        "cv": {
            "summary": "Senior backend engineer with 8 years of experience architecting microservices for a high-volume payments platform.",
            "experience": [
                "Lead Backend Engineer, PaySecure Holdings, 2020-Present - Architected microservices platform processing millions of dollars monthly; mentor team of 4 junior developers.",
                "Senior Backend Developer, PaySecure Holdings, 2017-2020 - Built core transaction processing services in Java/Spring Boot.",
                "Backend Developer, Lanka Software Solutions, 2015-2017 - Built internal business tools in Java.",
            ],
            "education": "BSc Computer Science, University of Colombo School of Computing, 2015",
            "extra_skills": "Apache Kafka, event-driven architecture, system design mentorship, production incident response",
        },
    },
    {
        "full_name": "Vinuki Chandrasena", "email": "vinuki.chandrasena@example.com",
        "role_wanted": "Data Scientist", "location": "Colombo, Sri Lanka",
        "experience_level": "Entry",
        "skills": "Python, pandas, scikit-learn, Statistics, SQL",
        "cover_letter": (
            "I recently finished my Master's with a thesis on demand forecasting using time "
            "series models, and I've done a short internship applying similar techniques to "
            "retail inventory data. I'm eager to apply academic rigor to real business "
            "problems and keep learning from experienced data scientists."
        ),
        "cv": {
            "summary": "Entry-level data scientist with a Master's thesis in time series forecasting and retail analytics internship experience.",
            "experience": [
                "Data Science Intern, RetailIQ Analytics, 2024 - Built demand forecasting models for retail inventory, applying time series techniques from academic research.",
                "Research Assistant, University of Colombo School of Computing, 2023-2024 - Thesis on time series demand forecasting models.",
            ],
            "education": "MSc Data Science, University of Colombo School of Computing, 2024",
            "extra_skills": "Time series analysis (ARIMA, Prophet), Jupyter, data cleaning and EDA",
        },
    },
]


def _make_cv_pdf(persona):
    """Build a genuine multi-section text PDF for a candidate - real
    readable content the AI can meaningfully summarize, not a placeholder.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    x = 1 * inch
    y = height - 1 * inch
    line_height = 16

    def write_line(text, size=10, bold=False, gap=line_height):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, text)
        y -= gap

    def wrap_and_write(text, size=10, max_width=6.3 * inch):
        nonlocal y
        c.setFont("Helvetica", size)
        words = text.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if c.stringWidth(test_line, "Helvetica", size) > max_width:
                c.drawString(x, y, line)
                y -= line_height
                line = word
            else:
                line = test_line
        if line:
            c.drawString(x, y, line)
            y -= line_height

    write_line(persona["full_name"], size=16, bold=True, gap=22)
    write_line(f"{persona['role_wanted']}  |  {persona['location']}", size=11, gap=20)
    write_line(f"Email: {persona['email']}", size=9, gap=20)

    write_line("SUMMARY", size=11, bold=True, gap=16)
    wrap_and_write(persona["cv"]["summary"])
    y -= 8

    write_line("WORK EXPERIENCE", size=11, bold=True, gap=16)
    for entry in persona["cv"]["experience"]:
        wrap_and_write(entry)
        y -= 4
    y -= 8

    write_line("EDUCATION", size=11, bold=True, gap=16)
    wrap_and_write(persona["cv"]["education"])
    y -= 8

    write_line("SKILLS", size=11, bold=True, gap=16)
    wrap_and_write(persona["skills"] + ". " + persona["cv"]["extra_skills"])

    c.save()
    buf.seek(0)
    return buf.read()


def seed(app=None):
    """Create all seed candidates. If an app instance is passed in (e.g.
    when called from the app factory's startup hook), reuse it instead of
    creating a second one.
    """
    owns_app = app is None
    if owns_app:
        app = create_app()

    created = 0
    skipped = 0

    with app.app_context():
        for persona in CANDIDATES:
            existing = User.query.filter_by(email=persona["email"]).first()
            if existing:
                print(f"SKIP  {persona['full_name']} - account already exists")
                skipped += 1
                continue

            user = User(email=persona["email"], role="candidate")
            user.set_password("TalentHub2026!")
            db.session.add(user)
            db.session.flush()  # get user.id without a full commit yet

            pdf_bytes = _make_cv_pdf(persona)
            cv_filename = f"seed_{user.id}_{persona['full_name'].split()[0].lower()}_cv.pdf"

            import os
            upload_folder = app.config["UPLOAD_FOLDER"]
            os.makedirs(upload_folder, exist_ok=True)
            with open(os.path.join(upload_folder, cv_filename), "wb") as f:
                f.write(pdf_bytes)

            profile = CandidateProfile(
                user_id=user.id,
                full_name=persona["full_name"],
                role_wanted=persona["role_wanted"],
                skills=persona["skills"],
                location=persona["location"],
                experience_level=persona["experience_level"],
                contact_email=persona["email"],
                cover_letter=persona["cover_letter"],
                cv_filename=cv_filename,
            )
            db.session.add(profile)
            db.session.commit()

            print(f"CREATED  {persona['full_name']} ({persona['experience_level']}, {persona['role_wanted']})")
            created += 1

    print(f"\nDone. Created {created}, skipped {skipped} (already existed).")
    print("All seeded accounts use the password: TalentHub2026!")


if __name__ == "__main__":
    seed()
