# Transcritor de Áudio de Zap — Referência do Projeto (v2.1)

## Stack

- **Python 3.10+** (desenvolvido em 3.14)
- **customtkinter 6.x** — UI com tema claro/escuro automático (segue o Windows)
- **tkinterdnd2** — drag & drop nativo Windows
- **requests** — chamadas HTTP à API (OpenAI ou endpoint compatível v1)
- **pygame-ce + mutagen + pyogg** — player de áudio embutido (duração, seek, Opus→WAV)
- **PyInstaller** — empacotamento em `.exe` standalone

---

## Estrutura de arquivos

```
transcricao_app.py       # app completo (single file)
requirements.txt         # dependências pinadas (builds reproduzíveis)
transcritor.spec         # spec portável do PyInstaller (sem paths absolutos)
version_info.txt         # VSVersionInfo do Windows (propriedades do exe)
build.ps1                # gera dist\transcrizap.exe  [-Zip: pacote p/ envio]
distribuicao/LEIA-ME.txt    # texto (pt-BR) que acompanha o zip enviado a colaboradores
distribuicao/README-EN.txt  # mesmo texto em inglês (não empacotado pelo build.ps1 hoje)
assets/icone.ico          # logo (balão de conversa âmbar + forma de onda) — exe e janela
README.md                 # porta de entrada em inglês (GitHub)
README.pt-BR.md           # tradução em português
LICENSE                   # MIT
PROJETO.md                # esta referência técnica interna (pt-BR)
N8N_REFERENCIA.md         # histórico do workflow n8n que deu origem ao app
```

---

## Identidade visual (v2.1 — decisão de design)

**Conceito: estúdio de gravação.** O assunto do app é som virando texto; o design vem do mundo do áudio.

- **Paleta**: grafite neutro + **âmbar de VU/fita** como única cor viva. Toda cor é tupla `(light, dark)`.

```python
BG           = ("#f2f3f5", "#101113")
SURFACE      = ("#ffffff", "#17191c")
SURFACE2     = ("#e8eaed", "#1f2226")
ACCENT       = ("#b25e09", "#f5a524")   # âmbar: agulha de VU, saturação de fita
ACCENT_HOVER = ("#8f4c07", "#ffbf55")
ON_ACCENT    = ("#ffffff", "#161311")   # texto sobre o âmbar
TEXT         = ("#191a1c", "#f2f3f5")
MUTED        = ("#6f7379", "#979da6")
SUCCESS      = ("#177245", "#4ade80")
DANGER       = ("#b3261e", "#f87171")
BORDER       = ("#dfe1e5", "#292d32")
WAVE_IDLE    = ("#c9ccd2", "#383d44")
```

- **Assinatura: forma de onda em barras** (`WaveStrip` + `_waveform_heights`). Cada arquivo tem uma onda única e estável, derivada dos bytes (assinatura visual, não amplitude real). O mesmo motivo aparece três vezes, sempre com função: convite no dropzone (pulsa ao arrastar por cima), progresso pulsante no card enquanto transcreve (substitui barra de progresso genérica) e barra de seek do player.
- **Tipografia em 3 camadas**: Segoe UI Variable **Display** (wordmark, "Solte o áudio aqui"), Variable **Text** (conteúdo), **Cascadia Mono** (dados e chrome: tempos, contadores, status, navegação, eyebrows das configurações em MAIÚSCULO). Fallbacks: Segoe UI / Consolas. `SetProcessDpiAwareness(2)` para nitidez.
- **Sem emoji colorido** — só glifos geométricos: ▶ ⏸ ● ✕ ◐ ○ ▸ ▾.
- **Logo**: balão de conversa âmbar (o "zap") com barras de onda grafite dentro (o áudio). Gerada por script PIL; `assets/icone.ico` entra no exe (ícone) e na janela (`iconbitmap` via `sys._MEIPASS`).
- **Barra de título** acompanha o tema (DwmSetWindowAttribute 20).
- **Tema manual**: botão no header cicla ◐ auto → ○ claro → ● escuro; persiste em `config.json` (`appearance`).

### Layout

- Header fino: wordmark `● transcritor de áudio de zap` + botões mono minúsculos (tema, ajustes, log) + status `● pronto / ● processando… / ● falta a chave` (clicável quando falta chave).
- **Dropzone-herói**: sem cards, ocupa a página inteira, sem caixa (borda âmbar só ao arrastar por cima); com cards, colapsa para barra fina de 46px. A área de cards só é montada quando existe card (sem scrollbar solta).
- Cards compactos: nome + ✕, meta em mono (`0:42 · 1.234 caracteres`), onda pulsante com etapa (`enviando ao Whisper…` / `limpando com GPT…`) que vira player ao concluir, textbox de altura dinâmica, ações Copiar (primário) / Salvar .txt / Reescrever.
- Sem `CTkTabview`: páginas trocadas por pack/pack_forget; botão ativo fica âmbar.
- **Footer**: crédito discreto abaixo das páginas (`_build_footer()`), com o texto traduzido `footer_offer` + link clicável "Felipe Drummond" (`webbrowser.open(GITHUB_URL)`, `GITHUB_URL = "https://github.com/ffapd1989"`). O ícone é um Octocat simplificado desenhado em PIL (`_github_image()`, mesma técnica 8x + `Image.LANCZOS` do chevron), com variante de cor por tema (`ACCENT` claro/escuro).

### Dropdown próprio (substitui `CTkOptionMenu`)

O `CTkOptionMenu` desenha a seta em canvas e ela sai serrilhada em telas de alta densidade. A classe `Dropdown(ctk.CTkFrame)` resolve isso com um campo próprio: `CTkLabel` com o valor à esquerda + chevron nítido à direita + `tk.Menu` nativo para a lista de opções (posicionado com `tk_popup` logo abaixo do campo).

O chevron nítido vem de `_chevron_image()`: renderizado em PIL numa tela **8x** maior (`ImageDraw.line` com `joint="curve"` + círculos nas pontas) e reduzido com `Image.LANCZOS` — anti-aliasing real, em vez do serrilhado do canvas do Tkinter. O resultado é um `CTkImage` com `light_image`/`dark_image` (variante por tema), cacheado em `_chevron_cache` (calculado uma vez, reaproveitado em todos os dropdowns). O ícone do GitHub no footer usa a mesma técnica (`_github_image()` / `_github_cache`).

Usado em: Modelo Whisper, Idioma do áudio, Modelo GPT, Idioma da interface.

---

## Segurança da chave de API (decisão de produto)

**A chave nunca vai para arquivo de texto.** Ela mora no **Gerenciador de Credenciais do Windows** (Credential Manager, cifrado com DPAPI pela conta do usuário) — mesmo padrão do cofre do plugin transcritranslator do Stream Deck:

- Cofre em `vault_read()` / `vault_write()` / `vault_delete()` — ctypes + advapi32 (`CredReadW`/`CredWriteW`/`CredDeleteW`), target `TranscritorDeAudio/OpenAI`, sem dependência extra. A credencial aparece em Painel de Controle → Gerenciador de Credenciais → Credenciais Genéricas.
- `DEFAULT_CONFIG` não tem `api_key`; `save_config()` faz `pop("api_key")` numa cópia antes de gravar o JSON.
- **Migração/scrub:** se um `config.json` antigo contiver `api_key`, `load_config()` remove a chave e regrava o arquivo imediatamente; o `App` grava essa chave no cofre (migração automática).
- Persistência no cofre ao clicar "Salvar configurações" **e** automaticamente ao iniciar uma transcrição (se a chave do campo difere da guardada).
- Botão "Esquecer chave" nas Configurações apaga do cofre e limpa o campo.
- Botão "Testar chave" (`ConfigPanel._test_key`) faz `GET {base}/models` com a chave do campo (não precisa ter salvo antes), em thread separada; reporta chave válida (com contagem de modelos, se o corpo da resposta trouxer `data`), inválida (HTTP 401), timeout ou falha de conexão. Não grava nada — só valida.
- A thread de transcrição recebe a chave como **snapshot** (parâmetro), não referência ao cfg.

---

## Arquitetura do app

### Classes principais

```
App (ctk.CTk)
├── DropZone (ctk.CTkFrame)           — herói sem caixa (vazio) / barra fina (com cards)
├── TranscriptionCard (ctk.CTkFrame)  — header, meta mono, onda pulsante → player, ações
├── AudioPlayer (ctk.CTkFrame)        — botão redondo + WaveStrip de seek + tempo mono
├── WaveStrip (tk.Canvas)             — barras de onda: decor, pulso e seek (tema vivo)
├── Dropdown (ctk.CTkFrame)           — seletor próprio (substitui CTkOptionMenu — ver seção Dropdown)
└── ConfigPanel (ctk.CTkScrollableFrame) — chave no cofre, endpoint, grid 2 col, prompt colapsável
```

### Fluxo de execução

```
on_files([paths])           # ACRESCENTA aos pendentes (dedup) — não substitui
  └── _on_submit()          # valida chave; persiste no cofre se mudou
        └── _dispatch(path) # card imediato + thread
              └── _run_transcription(path, card, api_key_snapshot)
                    ├── transcribe_audio()   # etapas viram card.set_stage(...)
                    │     ├── POST {base}/audio/transcriptions  (Whisper)
                    │     └── POST {base}/chat/completions      (GPT, se cleanup=True)
                    ├── card.set_result(texto)  → onda vira AudioPlayer
                    └── card.set_error(msg)
```

Threads nunca tocam a UI diretamente — todo retorno via `self.after(0, ...)`.

### Performance

- Poll do player a 180ms **só enquanto toca**; pulso da onda a 90ms só enquanto transcreve.
- Log com buffer + flush agrupado via `after(120ms)`.
- `AudioPlayer` criado lazy; onda (`_waveform_heights`) calculada uma vez por card e reaproveitada no player.
- Textbox de altura dinâmica: `min(320, max(96, linhas_estimadas*21+24))`.

---

## Configurações

Salvas em `%APPDATA%\TranscricaoApp\config.json` (**sem** `api_key` — ver acima).

| Campo | Tipo | Default |
|---|---|---|
| `appearance` | str | `"system"` (`system`/`light`/`dark`) |
| `ui_language` | str | `"auto"` (`auto`/`pt`/`en`/`es` — ver seção Internacionalização) |
| `base_url` | str | `"https://api.openai.com/v1"` |
| `whisper_model` | str | `"gpt-4o-mini-transcribe"` (recomendado; whisper-1 é migrado no boot) |
| `gpt_model` | str | `"gpt-4.1-nano"` (recomendado) |
| `language` | str | `"auto"` — Whisper detecta; qualquer outro valor fixa o idioma |
| `apply_cleanup` | bool | `true` |
| `cleanup_prompt` | str | `""` — vazio = usar o prompt padrão do idioma; só personalização é gravada |

`load_config()` faz merge com `DEFAULT_CONFIG` para não quebrar com campos novos.

### Idioma do áudio e prompts de limpeza

- **Idioma do áudio: `auto` por padrão** (o Whisper detecta). O seletor é **replicado na tela principal** (linha acima do dropzone) e nos ajustes, compartilhando a **mesma `StringVar`** (`App.audio_lang_var`, injetada no `ConfigPanel` via `lang_var=`) — mudar num lugar reflete no outro na hora, e o prompt padrão acompanha.
- **`CLEANUP_PROMPTS`** traz o prompt de limpeza em 8 idiomas: `pt` (o original, com as regras afinadas do autor, inclusive a nota sobre o falar carioca), `en`, `es`, `fr`, `de`, `it`, `ja`, `zh`.
- **`prompt_lang(cfg)`** decide o idioma do prompt: segue o **idioma da UI**; quando o áudio está fixado num idioma que a UI não cobre (`fr`, `de`, `it`, `ja`, `zh`), esse vence — é o idioma do texto que será limpo.
- **Personalização vence sempre.** `is_custom_prompt()` considera personalizado qualquer texto diferente de todos os padrões; nesse caso o prompt nunca é trocado automaticamente. `collect()` grava `""` quando o texto é um dos padrões, para o prompt continuar acompanhando o idioma. O botão "Restaurar padrão" volta ao padrão do idioma corrente, e uma legenda em mono diz qual dos dois estados está valendo.
- **Migração:** config antigo com o prompt padrão gravado em texto é normalizado para `""` no boot (volta a acompanhar o idioma); prompts realmente personalizados são preservados.

## API usada

Endpoint configurável (`base_url`, qualquer serviço compatível com OpenAI v1; vazio = OpenAI):

```
POST {base}/audio/transcriptions   # multipart: model, response_format=text, language, file
POST {base}/chat/completions       # limpeza (temp 0.2) e reescrita (temp 0.4)
```

Limite da API Whisper: **25 MB** por arquivo (validado antes do envio).

## Formatos de áudio suportados

`.mp3` `.mp4` `.m4a` `.ogg` `.oga` `.opus` `.wav` `.webm` `.flac`

Inclui áudios do WhatsApp (`.ogg`/`.opus`). Opus é convertido para WAV temporário (pyogg) para o player — o SDL2 não decodifica OGG/Opus.

---

## Internacionalização (i18n)

A interface (não o log, que permanece técnico em pt-BR) é traduzida em três idiomas: português, inglês e espanhol.

- **Dicionário `I18N`**: `dict[str, tuple[str, str, str]]`, chave → tupla `(pt-BR, en, es-419)`. Cada string visível da UI (labels, botões, mensagens de status, textos de erro) tem uma entrada aqui.
- **Função `tr(key, **fmt)`**: resolve a tupla para o idioma corrente (`UI_LANG`, global do módulo) e aplica `.format(**fmt)` quando há placeholders (ex.: `tr("test_valid", n=8)`, `tr("err_too_big", mb="27.3")`). Fallback para inglês se `UI_LANG` não for `pt`/`en`/`es`.
- **Detecção**: `_detect_windows_ui_lang()` lê o idioma de exibição do Windows via `ctypes.windll.kernel32.GetUserDefaultUILanguage()` + `locale.windows_locale`, mapeando para `pt`/`es`/**fallback `en`** para qualquer outro idioma do sistema.
- **Resolução**: `resolve_ui_lang(cfg)` — se `cfg["ui_language"]` for `pt`/`en`/`es`, usa direto; se for `"auto"` (default), usa a detecção do Windows.
- **Config `ui_language`**: `"auto" | "pt" | "en" | "es"`, selecionável no dropdown "Idioma da interface" (seção Interface do `ConfigPanel`, com nomes amigáveis em `UI_LANG_NAMES`).
- **Troca ao vivo, sem reiniciar**: o seletor fica no **rodapé, canto direito** (`LangPicker`, cada opção escrita no próprio idioma: Auto (Windows) / Português / English / Español). Ao escolher, `App._ui_lang_picked()` → `apply_ui_language()`: redefine `UI_LANG`, salva o config, **reconstrói só o `ConfigPanel`** (são dezenas de rótulos — mais barato recriar preservando chave, prompt e estado do expander) e chama `retranslate()` no header, dropzone, ações globais, log, rodapé e em cada card. Cards e transcrições em andamento são preservados — nada é perdido na troca.

---

## Build e distribuição

```powershell
.\build.ps1          # dist\transcrizap.exe
.\build.ps1 -Zip     # + Transcritor-de-Audio-de-Zap-v2.2.1-win64.zip (exe + LEIA-ME.txt)
```

Decisões do `transcritor.spec`:
- **Portável** — nada de caminhos absolutos; `collect_all`/`collect_dynamic_libs` resolvem sozinhos.
- **`upx=False`** — UPX é gatilho clássico de falso-positivo em antivírus; péssimo para enviar a amigos.
- **`version_info.txt`** — propriedades do exe em pt-BR (ajuda SmartScreen/confiança).
- **Ícone** — `assets/icone.ico` vai para o exe **e** para `datas` (janela do app).
- **`email` não entra nos excludes** — `http.client` (usado pelo requests) depende dele.
- **Workpath fora do projeto** (`%LOCALAPPDATA%\Temp\transcritor-build`) — o Google Drive trava temporários recém-criados e quebrava o `--clean`.

Quem recebe o zip: descompactar e executar. SmartScreen vai avisar (exe sem assinatura) — "Mais informações → Executar assim mesmo". Instruções completas no `LEIA-ME.txt`.

---

## Known issues

- **OGG/Opus no player:** a transcrição funciona sempre; a reprodução depende do pyogg conseguir decodificar (fallback silencioso se falhar).

## Histórico

- **v2.1** — identidade visual "estúdio" (âmbar + forma de onda por arquivo, logo, tipografia em 3 camadas), tema manual ◐/○/●, endpoint compatível OpenAI v1, dropzone-herói, nome novo "Transcritor de Áudio de Zap"; interface multilíngue (i18n pt/en/es, auto-detecção do idioma do Windows com fallback inglês, config `ui_language`); botão "Testar chave" (`GET {base}/models`); `Dropdown` próprio com chevron anti-aliased em PIL/LANCZOS (substitui o `CTkOptionMenu` serrilhado); footer com crédito e link para o GitHub do autor (ícone Octocat em PIL); idioma do áudio seguindo o Windows na primeira execução e prompt de limpeza em 8 idiomas acompanhando o idioma (com personalização preservada).
- **v2.0** — chave no Gerenciador de Credenciais (nunca em texto plano) + scrub de configs antigos; tema claro/escuro automático; fim dos emoji; empacotamento portável (spec sem paths absolutos, version info, `-Zip`); corrigido o segundo drag & drop que substituía em vez de acrescentar.
- **v1** — app original derivado do workflow n8n (ver `N8N_REFERENCIA.md`).

## TODOs / possíveis melhorias

- [ ] `build.ps1 -Zip` empacota só o `distribuicao/LEIA-ME.txt`; incluir também o `README-EN.txt` quando o destinatário não for brasileiro
- [ ] Contador de tokens / custo estimado por transcrição
- [ ] Cópia automática para a área de transferência ao terminar (toggle)
- [ ] Divisão automática de arquivos > 25 MB
