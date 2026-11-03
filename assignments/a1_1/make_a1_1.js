const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle
} = require('docx');
const fs = require('fs');

const ACCENT = "1F4E79", LIGHT = "DEEAF6", GREY = "F2F2F2";
const W = 9360;

function h1(t){ return new Paragraph({ text: t, heading: HeadingLevel.HEADING_1, spacing:{before:280,after:140} }); }
function h2(t){ return new Paragraph({ text: t, heading: HeadingLevel.HEADING_2, spacing:{before:200,after:100} }); }
function p(t,o={}){ return new Paragraph({ spacing:{after:100}, ...o, children:[new TextRun({text:t, size:22, ...o.run})] }); }
function bullet(t){ return new Paragraph({ bullet:{level:0}, spacing:{after:60}, children:[new TextRun({text:t,size:22})] }); }

function cell(text, widthDxa, opts={}){
  return new TableCell({
    width:{size:widthDxa, type:WidthType.DXA},
    shading: opts.shade ? {type:ShadingType.CLEAR, fill:opts.shade, color:"auto"} : undefined,
    margins:{top:80,bottom:80,left:120,right:120},
    children:[new Paragraph({ children:[new TextRun({text:String(text), size:21, bold:!!opts.bold,
      color: opts.head ? "FFFFFF" : "000000"})]})]
  });
}

function table(headers, rows, widths){
  return new Table({
    width:{size:W, type:WidthType.DXA},
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader:true, children: headers.map((h,i)=>cell(h,widths[i],{bold:true,head:true,shade:ACCENT})) }),
      ...rows.map((r,ri)=> new TableRow({ children: r.map((c,i)=>cell(c,widths[i],{shade: ri%2 ? GREY : undefined})) }))
    ]
  });
}

const doc = new Document({
  styles:{ default:{ document:{ run:{ font:"Calibri", size:22 } },
    heading1:{ run:{ font:"Calibri", size:30, bold:true, color:ACCENT },
               paragraph:{ border:{ bottom:{style:BorderStyle.SINGLE, size:6, color:ACCENT, space:4} } } },
    heading2:{ run:{ font:"Calibri", size:25, bold:true, color:"2E74B5" } } } },
  sections:[{
    properties:{ page:{ margin:{ top:1080, bottom:1080, left:1080, right:1080 } } },
    children:[
      new Paragraph({ alignment:AlignmentType.CENTER, spacing:{after:60},
        children:[new TextRun({text:"21CSE525T — AGENT TECHNOLOGY", size:22, color:"595959", bold:true})]}),
      new Paragraph({ alignment:AlignmentType.CENTER, spacing:{after:60},
        children:[new TextRun({text:"Assignment 1.1 — Project Ideation, Environment Modeling & PEAS Matrix", size:32, bold:true, color:ACCENT})]}),
      new Paragraph({ alignment:AlignmentType.CENTER, spacing:{after:300},
        children:[new TextRun({text:"Design Specification Document", size:24, italics:true, color:"595959"})]}),

      h1("1. Domain Definition"),
      h2("1.1 Domain"),
      p("Education Technology (EdTech) intersecting Artificial Intelligence and Decision-Support Systems."),
      h2("1.2 Agent Persona"),
      p("The Placement Preparation Agent is an autonomous software agent that assists an engineering student through the campus-placement cycle. It continuously senses the student's coding, aptitude, core-subject and interview performance, reasons about the gap between the current state and the target company's requirements, and acts by generating, revising and enforcing a personalised preparation roadmap."),
      h2("1.3 Problem Statement"),
      p("Students preparing for campus placements face three compounding difficulties: (i) they cannot reliably identify which of their skills are weakest relative to a target company, (ii) they cannot allocate limited study hours optimally across coding, aptitude, core subjects and communication, and (iii) preparation plans go stale the moment the environment changes — a drive is announced early, a cut-off is revised, or a test score moves. Existing platforms deliver static, generic content and require the student to do the planning. The proposed agent closes this loop autonomously: it perceives change, re-deliberates, and re-plans without being asked."),
      h2("1.4 Scope and Goals"),
      bullet("G1 — Maintain an accurate, continuously-revised model of the student's skill state."),
      bullet("G2 — Maximise a defined placement-readiness utility subject to time and budget constraints."),
      bullet("G3 — Re-plan autonomously when the environment changes (new drive, revised cut-off, new score)."),
      bullet("G4 — Coordinate with external agents (mentor agents, placement-cell agent) to secure resources."),
      bullet("G5 — Reject unauthenticated or tampered instructions from untrusted hosts."),

      h1("2. PEAS Profile"),
      p("The PEAS framework specifies the task environment for a rational agent. The table below defines the complete PEAS profile for the Placement Preparation Agent."),
      table(
        ["Component","Specification for the Placement Preparation Agent"],
        [
          ["Performance Measure (P)",
           "Weighted placement-readiness score U = w1·skill_gain + w2·placement_boost + w3·mentor_quality + w4·cost_efficiency + w5·time_efficiency, subject to Σwi = 1. Secondary measures: number of tier-1/2 companies for which the student becomes eligible, reduction in skill-gap count against the target company, mock-interview rating improvement, plan-adherence ratio, and mean time-to-replan after an environmental change."],
          ["Environment (E)",
           "Student profile (CGPA, branch, backlog status); coding platforms (LeetCode, HackerRank) supplying solved-count and accuracy telemetry; aptitude testing engine; mock-interview mentors and their feedback; the campus placement cell publishing drive dates and eligibility cut-offs; a curated resource corpus (problem sheets, articles, question banks); the student's own calendar and available study hours; and a monetary training budget."],
          ["Actuators (A)",
           "Generate and publish a study plan; assign a graded problem ladder for a specific skill; schedule and book a mock-interview slot; issue reminder and nudge notifications; recommend learning resources; re-prioritise or drop an in-flight plan; dispatch signed negotiation messages (CFP, PROPOSE, ACCEPT, REJECT) to mentor agents; render the live CLI dashboard; and write revised beliefs back into the knowledge base."],
          ["Sensors (S)",
           "Coding-platform score and delta feed; aptitude test-result feed; mock-interview rating and mentor feedback; topic-completion and time-on-task signals; placement-cell drive announcements and cut-off updates; company eligibility criteria; resume and portfolio signals (e.g. GitHub public repository count via REST API); ambient context (date, days-to-drive, weather affecting the study modality); and inbound network messages from peer agents."]
        ],
        [2300, 7060]),

      h1("3. Environment Characteristics"),
      p("Classifying the task environment determines which agent architecture is appropriate. The classification below justifies the use of a deliberative BDI architecture layered over a reactive reflex core rather than a purely reflexive design."),
      table(
        ["Dimension","Classification","Justification"],
        [
          ["Observability","Partially Observable",
           "The agent senses scores, submissions and announcements, but cannot observe the student's motivation, retention quality, the recruiter's private evaluation rubric, or the questions that will actually be asked. The agent must therefore maintain an internal belief state rather than act on raw percepts alone."],
          ["Determinism","Stochastic",
           "The same preparation action does not yield a deterministic outcome. Interview results depend on panel subjectivity, competing candidates, and question sampling. Score improvements from a fixed study block vary."],
          ["Episodicity","Sequential",
           "Every action changes the state on which subsequent actions operate. Mastering recursion is a prerequisite for dynamic programming; a poor mock interview alters the plan for the following week. There are no independent episodes."],
          ["Dynamism","Dynamic",
           "The environment changes while the agent is deliberating: drives are advanced, cut-offs are revised, new companies register. The agent must re-deliberate mid-execution rather than compute a plan once."],
          ["Discreteness","Discrete",
           "Percepts, actions and time are discretised. The agent selects from a finite catalogue of topics, resources, mentors and time slots; scores are integers in [0,100]."],
          ["Agency","Multi-Agent (mixed cooperative / competitive)",
           "The core preparation loop serves a single student, but the agent negotiates with self-interested Mentor Agents (competitive, opposing utility) and cooperates with the Placement Cell Agent (shared goal). Peer student agents introduce competition for limited drive slots."],
          ["Knowledge","Known",
           "The transition and reward semantics are known to the designer: prerequisite relations, eligibility rules and utility weights are explicitly encoded in the ontology, even though outcomes remain stochastic."]
        ],
        [1700, 2100, 5560]),

      h1("4. Autonomous Agent vs. Standard Object-Oriented Program"),
      p("The following structural contrast establishes why this system is an agent rather than a conventional object-oriented application. Each row contrasts a defining agent property with the corresponding behaviour of an ordinary OO program."),
      table(
        ["Criterion","Autonomous Agent (this system)","Standard Object-Oriented Program"],
        [
          ["Thread of control","Owns its own thread of control. Daemon workers and the deliberation loop run continuously and initiate action independently.",
           "Control is owned by the caller. An object's method executes only when it is invoked from outside."],
          ["Invocation model","Proactive — decides for itself when and whether to act, and may refuse or defer.",
           "Reactive to invocation — a public method always executes when called; it cannot decline."],
          ["State semantics","Maintains beliefs: a revisable model of the world, updated from percepts, with revision history.",
           "Maintains fields: passive data with no notion of evidence, staleness or revision."],
          ["Goal orientation","Goal-directed. Holds desires with dynamic priority and commits to intentions to achieve them.",
           "Task-directed. Executes the specific function the programmer encoded; has no goal representation."],
          ["Adaptivity","Re-plans at runtime. A belief change can cause an in-flight intention to be dropped and replaced.",
           "Follows a fixed control flow. Changing behaviour requires editing and recompiling source code."],
          ["Environment coupling","Situated and persistent. Continuously senses and acts on the environment across its whole lifetime.",
           "Transient and decoupled. Reads inputs, computes, returns, and terminates."],
          ["Interaction model","Social. Communicates with other agents via a speech-act protocol (CFP / PROPOSE / ACCEPT / REJECT) and negotiates outcomes.",
           "Mechanical. Calls methods on other objects; no negotiation, no possibility of refusal or counter-offer."],
          ["Failure handling","Deliberative recovery — reconsiders desires and selects an alternative plan when an action fails.",
           "Exception propagation — throws upward and relies on the caller to decide what happens next."],
          ["Autonomy over data","Encapsulates behaviour and control. Decides whether to honour an incoming request, and authenticates its source.",
           "Encapsulates data only. Any caller holding a reference may invoke any public method."]
        ],
        [1600, 3980, 3780]),

      h1("5. Agent Architecture Overview"),
      p("The agent is implemented as a layered hybrid architecture. A reactive layer guarantees fast responses to urgent percepts, while a deliberative BDI layer performs goal reasoning over a longer horizon."),
      table(
        ["Layer","Unit","Responsibility"],
        [
          ["Security Gateway","5","Verifies HMAC-SHA256 signatures, host identity, freshness and role authorisation on every inbound message before it reaches the agent core."],
          ["Reactive Layer","1","Condition-action rule engine. Fires immediate responses to urgent percepts (imminent drive, collapsed score, idleness)."],
          ["Perception & Concurrency","2","Daemon worker threads poll external sources and publish signed percepts onto a thread-safe event bus; socket endpoints exchange serialised state with remote agents."],
          ["Social Layer","3","Contract-Net negotiation with mentor agents and constrained utility maximisation over the resource catalogue."],
          ["Deliberative Core","4","Belief base, desire set with dynamic priority, and an intention stack supporting mid-execution re-planning; backed by the domain ontology and live REST feeds."],
          ["Presentation","5.2","Live CLI dashboard rendering skill bars, active desires, current intention and security counters."]
        ],
        [2000, 900, 6460]),

      h1("6. Deliverable Mapping"),
      table(
        ["Rubric Component","Marks","Where satisfied in this document"],
        [
          ["Domain & Persona Clarity","1","Section 1 — domain, persona, problem statement, scope and goals."],
          ["PEAS Profile Completeness","2","Section 2 — full PEAS table; Section 3 — environment characteristics classification."],
          ["Agent vs. Object Structural Contrast","2","Section 4 — nine-criterion structural contrast table."]
        ],
        [3200, 900, 5260]),
    ]
  }]
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync('Assignment_1_1_Design_Specification.docx', b); console.log('written'); });
