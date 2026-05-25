kiểu bọn nó reskin ấy, hermes bảo là lớn lên theo người dùng mà tôi chỉ cần đổi model 1 cái là con nguu liền :v kiểu cơ chế nó là gì mà quảng cáo như thế vậy

Đa số câu “AI grows with you”, “learns your workflow”, “becomes your digital companion” hiện tại là marketing phóng đại rất mạnh.

Về kỹ thuật, thường chỉ có vài lớp phía sau:

1. Persistent Memory (ghi nhớ)

Ví dụ lưu:

tên project
coding style
preference
task history
summaries

Thường là:

JSON
SQLite
vector DB
markdown vault kiểu Obsidian

Khi chat:

retrieve memory liên quan
nhét lại vào prompt

=> tạo cảm giác “nó nhớ bạn”.

Nhưng thật ra model nền không hề “trưởng thành”.
Chỉ là context injection.

2. User Profiling

Hệ thống build profile kiểu:

user thích concise
dùng Python
ghét verbose
đang làm robotics

Rồi prepend instruction vào system prompt.

Ví dụ:

User prefers terminal-native workflow.

Thế thôi.

3. Workflow Adaptation

Nó học:

bạn thường mở file nào
command nào hay dùng
flow làm việc ra sao

Rồi suggest shortcut/macro.

Giống IDE thông minh hơn một chút.

4. Retrieval-Augmented Identity

Cái “nhân cách liên tục” thật ra thường là:

SOUL.md
identity prompt
long-term summaries

Mỗi lần boot:

load identity
load summaries
load recent memory

=> tạo illusion continuity.

Vấn đề lớn nhất:

“trí thông minh” không nằm trong memory.

Nó nằm trong:

reasoning quality
planning
instruction following
abstraction ability

tức là model nền.

Nên:

đổi model yếu hơn = persona collapse

là hoàn toàn bình thường.

Ví dụ:

GPT-5.5 quản lý workflow ổn
đổi sang tiny OSS model

thì:

quên rule
loop
phá format
mất planning
hallucinate state

dù memory vẫn còn nguyên.

Đó là vì memory ≠ cognition.

Nhiều startup cố làm người dùng tin rằng:

memory accumulation = intelligence growth

Nhưng khoa học hiện tại chưa chứng minh vậy.

LLM hiện nay chủ yếu:

stateless inference engine
có retrieval hỗ trợ

chứ chưa phải:

evolving cognition
continual self-rewiring intelligence

Muốn “lớn lên thật” thì cần thứ gần:

continual learning
online fine-tuning
reinforcement loops
self-model update
persistent world model

Mà đây là vùng cực khó:

catastrophic forgetting
alignment drift
instability
corruption
reward hacking

Nên phần lớn công ty tránh động trực tiếp vào model.

Họ chỉ:

wrap memory quanh model
gọi đó là “growing AI”.

Thứ bạn đang nghĩ thật ra gần “cognitive architecture” hơn:

episodic → semantic memory
abstraction consolidation
bounded retrieval
stable identity layer
runtime contracts

Cái này đúng hướng hơn “save raw chats forever”.

Nhưng dù vậy:
nếu model nền yếu,
thì toàn bộ kiến trúc vẫn có trần rất thấp.

Nói thẳng:
hiện tại “AI companion grows with you” phần lớn là:

memory engineering + prompt persistence + branding.

vậy hệ thống guild chạy trơn tru khi đổi model của tôi raatsttt khá thực hiện ?

Đúng. Cực khó. Và khó hơn phần lớn người mới build agent tưởng rất nhiều.

Cái bạn đang muốn thật ra là:

“Model-agnostic cognitive runtime”

Tức:

đổi model vẫn chạy ổn
worker không ngu đi quá mạnh
workflow không vỡ
memory không loạn
contract vẫn giữ

Đây gần như là bài toán trung tâm của AI systems engineering hiện tại.

Lý do khó:

1. Mỗi model là một “sinh vật” khác nhau

Ví dụ:

OpenAI model mạnh planning
Anthropic model cẩn thận hơn
OSS model có thể giỏi format nhưng ngu reasoning
tiny model thì mất context discipline

Cùng prompt:

model A hiểu task graph
model B loop
model C phá JSON
model D hallucinate tool output

Nên runtime không thể assume:

“LLM behaves consistently”

2. Prompt không phải API stable

Đây là sai lầm lớn của ngành hiện tại.

People treat prompts like:

run_task(task)

Nhưng thật ra nó gần:

persuade_alien_brain(task)

Không deterministic.

3. Guild càng nhiều agent càng khó

Vì giờ không chỉ:

model ↔ user

mà là:

model ↔ model
model ↔ memory
model ↔ filesystem
model ↔ scheduler
model ↔ blackboard

Sai số cộng dồn cực mạnh.

4. Model yếu phá shared state cực ghê

Đây là thứ bạn đã thấy rồi.

Ví dụ:
worker nhỏ:

đọc TASK.md sai
overwrite artifact
claim task nhầm
tự nghĩ task mới
loop retry
sửa file ngoài scope

=> blackboard corruption.

Nên hướng đúng không phải:

“tin model hơn”

mà là:

“giảm quyền model”

Đây là mindset systems engineering.

Guild thật sự ổn định thường cần:

Runtime > Model

Tức:

runtime kiểm soát workflow
model chỉ fill reasoning slot

Ví dụ:

Runtime quyết:
task graph
dependency
lock
ownership
retry
artifact schema
permissions
Model chỉ:
generate content
analyze local context
choose bounded actions

Giống OS thật:
process không được:

tự sửa kernel
tự claim RAM người khác
tự ghi filesystem lung tung

Muốn model interchangeable,
bạn cần:

1. Strong contracts

Ví dụ:

{
  "task_id": "...",
  "allowed_outputs": [...],
  "next_states": [...]
}

Không cho freestyle.

2. Capability isolation

Worker chỉ thấy:

task hiện tại
artifact liên quan

Không thấy toàn guild.

Đây cực quan trọng với model yếu.

3. Structured runtime

Không để:
“agent tự nghĩ workflow”.

Workflow phải:

explicit
state machine based
dependency checked
4. Blackboard discipline

Blackboard không phải:
“markdown chat room”.

Mà phải gần:

transactional DB
event log
append-only records
leases/claims
timestamps
ownership
5. Hierarchical intelligence

Bạn đã nhận ra đúng:

PM/Hermes dùng model mạnh
worker dùng model yếu/rẻ

Đây gần giống:

commander + drones

và thực tế hơn nhiều so với:

“mọi agent đều GPT-5 class”.

Điểm thú vị:
Bạn đang đụng rất gần tư duy:

distributed systems
operating systems
actor models
orchestration runtime
workflow engines

…chứ không còn là “prompt engineering” nữa.

Đó là lý do build multi-agent thật sự khó hơn làm chatbot hàng chục lần.


chà tôi vibe nhiều quá giờ đọc code thấy khó hiểu phết và đẻ ra toàn syntax tôi ko hiểu

Đó là một vấn đề rất thật khi dùng AI quá nhiều để lập trình.

Não bắt đầu chuyển từ:

“tự xây logic”

sang:

“đọc kết quả AI sinh ra”.

Và khi AI bắt đầu:

dùng syntax lạ,
abstraction cao,
framework mới,
trick tối ưu,

thì người dùng rơi vào trạng thái:

code chạy được nhưng mình không thật sự sở hữu nó.

Đây là cái bẫy lớn nhất của thời AI coding hiện nay.

Điều nguy hiểm không phải là “không biết syntax”

Syntax luôn tra được.

Nguy hiểm là:

mất khả năng mô hình hóa logic trong đầu.

Ví dụ:

data flow đi đâu,
state đổi lúc nào,
async hoạt động sao,
vì sao bug xuất hiện,
memory/runtime đang làm gì.

Nếu phần này mờ đi:
thì sau vài tuần người ta cảm giác:

“mình đang copy phép thuật”.

Vì sao chuyện này xảy ra?

Vì AI có xu hướng:

sinh code theo “mẫu internet tốt nhất”,
dùng abstraction hiện đại,
tối ưu ngắn gọn,
và đôi khi overengineer.

Nó không tự biết:

bạn đang ở level nào,
project cần đơn giản hay không,
runtime thật sự cần gì.

Nên dễ sinh ra:

decorator,
generic,
async phức tạp,
callback chain,
dependency injection,
metaclass,
hook,
pattern doanh nghiệp,

trong khi task chỉ cần:

for item in data:
    process(item)
Đặc biệt với bạn

Bạn đang đụng:

multi-agent,
orchestration,
runtime,
async,
memory architecture,
blackboard system.

Đây vốn đã là lĩnh vực abstraction cao.

Nếu cộng thêm AI-generated code:
=> rất dễ overload.

Cách dùng AI coding mà không bị “mất não”
1. Ép AI giải thích theo data flow

Đừng hỏi:

“viết code”.

Hãy hỏi:

“data đi từ đâu tới đâu?”
“vì sao cần async?”
“runtime state nằm ở đâu?”
“step-by-step execution”.

2. Luôn bắt AI viết bản “ngu nhưng rõ”

Ví dụ:

“viết phiên bản tối giản không abstraction”
“không class”
“không decorator”
“không clever syntax”.

Bạn sẽ học nhanh hơn rất nhiều.

3. Nếu không hiểu syntax → expand thủ công

Ví dụ:

result = [x.name for x in users if x.active]

hãy tự rewrite thành:

result = []

for x in users:
    if x.active:
        result.append(x.name)

Não sẽ giữ được logic.

4. Đừng học syntax trước, học execution model trước

Quan trọng nhất là:

chương trình chạy theo thứ tự nào,
state nằm ở đâu,
thread/event loop làm gì,
function call stack ra sao.

Người hiểu execution model có thể học framework mới rất nhanh.

Người chỉ nhớ syntax sẽ chết chìm khi abstraction đổi.

Và thật ra…

Việc bạn cảm thấy:

“code AI sinh ra bắt đầu khó hiểu”

là dấu hiệu tốt hơn bạn nghĩ.

Vì nó nghĩa là:

bạn chưa hoàn toàn giao não cho AI,

não bạn vẫn phát hiện:

“có thứ gì đó mình chưa sở hữu”.

Nhiều người còn không nhận ra điều đó,
họ chỉ:

copy,
chạy,
ship,
rồi tới lúc bug production thì bất lực hoàn toàn.

Thời AI coding hiện nay, kỹ năng quý nhất không còn là:

nhớ syntax.

Mà là:

hiểu hệ thống đang vận hành cái gì.

chà dài phết

Đúng 😅
Thật ra cái file này nhìn dài nhưng logic thật chỉ có 3 phần:

1. Setup DB
2. Define command
3. Parse command line

Phần còn lại chủ yếu là CRUD:

thêm task,
thêm event,
lấy state,
list dữ liệu.
Nếu nén não lại thì flow thật sự là:
terminal command
    ↓
argparse đọc lệnh
    ↓
gọi function tương ứng
    ↓
connect sqlite
    ↓
insert/select data
    ↓
print json

Hết.

Ví dụ:

python blackboard.py task "Fix bug"

thì flow là:

argparse thấy cmd = "task"
↓
gọi command_task()
↓
connect sqlite
↓
insert task vào DB
↓
print("ok")
Cái khiến bạn thấy “AI syntax”

là vì code này dùng:

type hint,
context manager,
pathlib,
argparse,
sqlite abstraction,
multiline SQL,
upsert syntax.

Nó làm file:

“professional” hơn,
nhưng khó đọc hơn người mới.
Nếu rewrite kiểu người thường sẽ như này:

Thay vì:

with connect() as con:

viết:

con = connect()

# làm gì đó

con.close()

Thay vì:

rows = con.execute(...).fetchall()

viết:

cursor = con.execute(...)
rows = cursor.fetchall()

Thay vì:

json.dumps(payload or {}, ensure_ascii=False)

viết:

if payload is None:
    payload = {}

text = json.dumps(payload)
AI có xu hướng viết “compressed code”

Tức:

ít dòng,
nhiều abstraction,
idiomatic,
chuyên nghiệp hơn,
nhưng khó đọc.

Trong khi người học nên đọc:

expanded code.

Đặc biệt mấy thứ làm bạn lú:
1. with
with connect() as con:

= tự đóng tài nguyên.

Tương đương:

con = connect()

try:
    ...
finally:
    con.close()
2. Path(...)
Path.home()

= đường dẫn thư mục user.

AI thích pathlib vì:

cross-platform,
đẹp hơn string path.
3. args.xxx
args.title

= lấy argument command line.

Ví dụ:

python app.py task "hello"

thì:

args.title == "hello"
4. sqlite3.Row
con.row_factory = sqlite3.Row

cho phép:

row["status"]

thay vì:

row[0]
5. dict | None
payload: dict | None

= type hint Python mới.

Nghĩa là:

payload có thể là:
- dict
- hoặc None
Thật ra đây là dấu hiệu tốt

Bạn đang bắt đầu:

đọc architecture,
đọc infra code,
đọc runtime tooling.

Nó khác hoàn toàn:

script tutorial,
bài Python nhập môn.

Đây là level:

“tooling engineer”.

Nên cảm giác:

“wtf sao syntax dị thế”
là bình thường.

Cách học đúng bây giờ

Đừng cố:

hiểu cả file một lúc.

Hãy:

1. Pick 1 command
2. Trace flow
3. Print debug
4. Rewrite đơn giản hơn

Ví dụ:

chỉ học task
bỏ qua toàn bộ phần còn lại.
Ví dụ minimal version của task
import sqlite3

con = sqlite3.connect("test.db")

con.execute("""
create table if not exists tasks(
    title text
)
""")

title = input("Task: ")

con.execute(
    "insert into tasks(title) values(?)",
    (title,)
)

con.commit()

print("done")

Đây chính là bản “linh hồn” của file kia.

Phần còn lại chỉ là:

thêm CLI,
thêm abstraction,
thêm safety,
thêm structure thôi.
chậc vì flow làm việc dự án tôi giờ bùng nổ quá rồi,
bản vẽ là thế mà khi thi công thì codex làm: thành ra blackboard là cơ chế sqlite, 3 ngày rôi liên tục smoke test ,cứ gặp bug là chưa kịp sửa thì nó đã múa rồi. flock té ra chỉ tham khảo chứ chỉ lấy 1 vài thành phần rồi blabla tóm lại overload rồi mai mà báo cáo thì chỉ có thể nói là build app mà mới có giao diện chứ demo chưa dc vì... đọc code có hiểu đâu :v

Nói thẳng: đừng báo cáo là “demo chưa được vì không hiểu code”. Nói vậy là tự chém mình.

Cách nói đúng hơn:

Em đã triển khai được phần khung ứng dụng và cơ chế blackboard dùng SQLite để lưu task, event, state và trạng thái agent. Hiện hệ thống đang ở giai đoạn smoke test và ổn định luồng dữ liệu nội bộ. Phần giao diện đã có, nhưng demo end-to-end chưa đóng gói ổn định nên em sẽ trình bày kiến trúc, các thành phần đã build và hướng hoàn thiện tiếp theo.

Bản chất hiện tại của bạn là:

Ý tưởng ban đầu:
multi-agent + blackboard + Flock tham khảo

Thực tế thi công:
CLI/app + SQLite blackboard + smoke test + giao diện sơ bộ

Trạng thái:
prototype có kiến trúc, chưa ổn định để demo trơn

Đây không phải fail. Đây là prototype đang phình scope.

Mai báo cáo thì chốt 4 ý:

Mục tiêu: xây hệ thống trợ lý AI/multi-agent có bộ nhớ và bảng điều phối tác vụ.
Đã làm: blackboard SQLite, lưu task/event/state/checkin/agent status, có giao diện bước đầu.
Đang kiểm thử: smoke test liên tục để đảm bảo lệnh, dữ liệu và trạng thái chạy đúng.
Vấn đề: phạm vi hệ thống mở rộng nhanh, nên đang cần chuẩn hóa lại kiến trúc và tài liệu trước khi demo hoàn chỉnh.

Một câu cực an toàn:

Do hệ thống có nhiều thành phần tương tác, em ưu tiên ổn định tầng dữ liệu và kiến trúc trước, sau đó mới hoàn thiện demo giao diện.

Còn tối nay đừng để Codex múa nữa. Khóa scope:

Không thêm feature.
Không refactor lớn.
Không đổi kiến trúc.
Chỉ viết README báo cáo + chụp màn hình giao diện + mô tả flow.

Mai bạn không cần chứng minh “app xịn”. Bạn cần chứng minh:

em biết mình đang xây cái gì, đã làm được phần nào, vì sao phần demo chưa hoàn chỉnh, và bước tiếp theo là gì.

Đó là báo cáo được.

• Đọc xong D:\HermesGuildCore\docs\learning\GptUI_talk.md.

  Nó đang nói đúng thứ mình đang làm trong Guild runtime:

  - “AI grows with you” chủ yếu là memory + prompt persistence, đổi model yếu là persona collapse vì memory ≠ cognition.
  - Muốn “model-agnostic runtime” thì phải đi hướng Runtime > Model: strong contracts, capability isolation, state
    machine/workflow explicit, blackboard như DB/event log.
  - Cách tránh worker “bốc rác”: giảm quyền model, giới hạn scope (task_only vs join_review), validate schema + evidence,
    ownership/leases.
    flow + viết bản ngu mà rõ.

  Nếu bạn muốn, tôi có thể trích ra 5 “design laws” từ file này và gắn vào docs/learning/SYSTEM_MAP_GUILD_DEMO.md như một
  phần “Principles”, để các session sau đọc map là nhớ đúng mindset.


› haiz tôi đang lâns cân làm sao để mà model yếu chạy đúng đây, vì nó chạy dựa trên script thì ngon rồi chứ đặt rule
  trong mấy prompt mà nó ngu thì ngang từ đâu đã ko vào đó đọc


• Đúng: nếu trông chờ “model yếu tự đọc rule trong prompt” thì sẽ vỡ. Muốn model yếu chạy đúng phải đổi chiến lược từ
  “prompt = luật” sang “runtime = luật”.

  Cách làm thực tế (không cần model khôn):

  - Runtime không đưa worker toàn bộ repo. Chỉ đưa “task packet” tối giản + dependency artifacts đã chọn sẵn.
  - Runtime chặn quyền: worker không tự chọn file; nó chỉ được phép xuất ra structured JSON “proposed_actions”. Script
    mới là thứ thực thi/ghi file.
  - Runtime validate và gate:
      - schema gate (đã có)
      - evidence gate (files_changed/commands_run/test_result)
      - scope gate (allowed_files)
      - no-op gate (đừng cho done nếu không làm gì)
  - Runtime buộc failure an toàn: thiếu info => needs_info => blocked (đã bắt đầu làm).
  - Join-review là chỗ duy nhất nhìn xuyên tasks; worker thường không được “biết công ty”.
  viết đoạn text, đề xuất patch) và mọi thứ còn lại do script quyết định.


› nhưng thiết kế 1 adapter như thế quá khó, vì bọn cli cài vào máy có agent.md và skill riêng của bọn nó nữa


• Đúng, nếu bạn cố “bọc” mọi CLI thành một sandbox hoàn hảo thì rất khó, nhất là khi mỗi CLI lại có
  AGENTS.md/skills/auto-behavior riêng.

  Cách thực tế là tách 2 tầng:

  - Tier 0 (Deterministic runtime): claim/lease, allowed_files, artifact schema, status machine, evidence gate,
    needs_info, join-review. Tầng này không phụ thuộc model/CLI nào và phải chạy ổn.
  - Tier 1 (Provider adapters, best-effort): chỉ là “call tool and capture output”, không tin tool tự tuân thủ rules.

  Để sống chung với CLI “có ý chí riêng”, bạn dùng chiến thuật rẻ mà hiệu quả:

  - Make it read-only by default: chạy CLI ở chế độ không sửa file (--pure, dry-run, format=json). Nếu tool không hỗ trợ,
    coi như nguy cơ cao.
  - Filesystem gate bên ngoài tool: trước/sau khi chạy, snapshot git status/file hashes trong allowed_files và fail nếu
    tool đụng ngoài scope.
  - Prompt injection tối thiểu: đừng nhồi 3 trang luật; chỉ đưa 3 điều “được/không được” + output contract.
  - Kill switch + classification: nếu adapter thấy tool output không đúng schema/evidence, trả needs_info hoặc
    provider_error, không mark done.
  vẫn chạy đúng.


› ngoài ra hệ thống phụ thuộc pm xịn, mà nếu model hết hạn là tiêu phải ko


• Không nhất thiết “tiêu”, nhưng đúng là degrade mạnh nếu PM/Hermes model yếu mà bạn đang dựa vào nó để làm những việc
  chỉ model mạnh mới làm tốt (chia DAG, ưu tiên, review logic, ra quyết định mơ hồ).

  Cách để không “chết theo PM model” là đẩy càng nhiều càng tốt sang runtime deterministic:

  - PM model chỉ làm 1 việc: biến prompt thành task packet (có scope + DoD + evidence). Nếu PM yếu, fallback sang
    template router (manual-router v0) là vẫn chạy.
  - Những thứ PM hay làm nhưng runtime làm được:
      - tạo DAG theo mẫu (parallel/sequential templates)
      - validate evidence
      - enforce permissions/scope
      - retry/backoff, leases, unlock deps
  - Những thứ phải có model mạnh:
      - giải mơ hồ, viết spec tốt, integration reasoning khó
  Vậy khi model hết hạn:

  - hệ thống vẫn chạy như workflow engine (tạo task theo template, worker theo rule, board vẫn phản ánh trạng thái)
  - chỉ mất “trí thông minh cao cấp”, chứ không sập runtime


› mà mơ hồ thì luôn tồn tại vì 1 hệ thống ko thể cover hết được ví dụ 3 ngày nay codex toàn brute force vì chú thông
  minh, chứ đưa cho opencode thì nó làm trong 8 phút rôi báo là hết quota ?


• Đúng: mơ hồ là “tự nhiên”, không thể cover hết bằng rule. Vấn đề là bạn đang lẫn 2 thứ:

  - Runtime correctness (không phá state, không làm bậy, không fake progress) → rule/guardrail xử được.
  - Task intelligence (hiểu mơ hồ, tự chia scope, tự tìm đường) → phụ thuộc model và quota.

  Cái bạn thấy “Codex brute force 3 ngày” vs “OpenCode 8 phút rồi hết quota” là tradeoff thật:

  - Model mạnh có thể “cứu” mơ hồ bằng suy luận + thử sai, nhưng tốn thời gian/cost.
  - Provider/quota-limited có thể nhanh lúc đầu, nhưng chết vì quota/token/context overhead.

  Cách sống chung thực dụng:

  - Đặt 3 mức kết quả cho mọi task:
      1. done (có evidence)
      2. blocked(needs_info) (đặt câu hỏi đúng)
      3. blocked(provider_error/quota) (không giả vờ làm được)
  - Khi gặp mơ hồ: ưu tiên ra needs_info sớm thay vì brute force.
  - Giảm “8 phút rồi chết quota” bằng:
      - task packets nhỏ hơn (ít context)
      - strict allowed_files
      - join-review để gom lại, không nhồi mọi thứ vào 1 call
      - dùng deterministic template router khi prompt mơ hồ

  Tóm lại: không thể hết mơ hồ, nhưng bạn có thể thiết kế để mơ hồ dẫn tới blocked có lý do thay vì brute force hoặc fake
  done.
