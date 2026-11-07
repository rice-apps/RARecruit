## Project Architecture Diagram:

```mermaid

flowchart TB
    subgraph S1["<b>Clients</b>"]
        Candidate([Candidate])
        Interviewer(["Interviewers & board"])
    end

    subgraph S2["<b> Frontend: Next.js + Tailwind</b>"]
        CandUI["<b>Candidate pages</b><br/>sign-up, reserve, reschedule, cancel"]
        IntUI["<b>Interviewer pages</b><br/>availability, written apps, candidates, interviews, stats"]
    end

    subgraph S3["<b> Backend: FastAPI </b>"]
        Roles["<b>Auth & roles</b><br/>verify JWT, interviewer lookup"]
        subgraph Mods[" "]
            Config["<b>Config</b><br/>dates, slot lengths, roles, rubric"]
            Sched["<b>Scheduling</b><br/>slots from availability, load balancing, bookings"]
            Intake["<b>Intake</b><br/>form import, reviewer assignment"]
            Grading["<b>Grading</b><br/>written app reviews, interview scores"]
            Stats["<b>Stats</b><br/>aggregates for written app + interview pages"]
        end
    end

    subgraph S4["<b>Data + auth: Supabase</b>"]
        Auth["Supabase Auth<br/>Google sign-in"]
        DB[("Postgres")]
    end

    subgraph S5["<b>External: Google</b>"]
        Forms["Forms API"]
        Calendar["Calendar API"]
    end

    Candidate --> CandUI
    Interviewer --> IntUI
    S2 -.->|Google sign-in| Auth
    S2 --> Roles
    Roles -->|verify JWT| Auth
    Roles --> Mods
    Mods <-->|service-role key| DB
    Intake <-.->|import responses: push or poll TBD| Forms
    Sched -->|create / update / cancel events| Calendar

    classDef clients fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,stroke-width:2px

    classDef frontend fill:#CFFAFE,stroke:#0891B2,color:#164E63,stroke-width:2px

    classDef backend fill:#DCFCE7,stroke:#16A34A,color:#14532D,stroke-width:2.5px

    classDef data fill:#FEF3C7,stroke:#D97706,color:#78350F,stroke-width:2px

    classDef external fill:#FCE7F3,stroke:#DB2777,color:#831843,stroke-width:2px

    class Candidate,Interviewer clients
    class CandUI,IntUI frontend
    class Roles,Config,Sched,Intake,Grading,Stats backend
    class Auth,DB data
    class Forms,Calendar external

    style S1 fill:#F0F7FF,stroke:#93C5FD,stroke-width:1.5px,color:#1E3A8A

    style S2 fill:#F0FDFF,stroke:#67E8F9,stroke-width:1.5px,color:#164E63

    style S3 fill:#F0FDF4,stroke:#86EFAC,stroke-width:2px,color:#14532D

    style Mods fill:#F0FDF4,stroke:#86EFAC,stroke-width:1px,stroke-dasharray:4 3

    style S4 fill:#FFFBEB,stroke:#FCD34D,stroke-width:1.5px,color:#78350F

    style S5 fill:#FDF2F8,stroke:#F9A8D4,stroke-width:1.5px,color:#831843

    linkStyle default stroke:#64748B,stroke-width:1.7px

```

### Other rules

- The frontend uses Supabase **only for sign-in**. Every data R/W is through FastAPI. FastAPI enforces candidate vs. interviewer access.
- Candidates can only reach Scheduling.
- The Supabase service-role key lives only in the backend.
- Calendar invites are sent **only** by the backend , whenever a booking is created, changed or cancelled.
