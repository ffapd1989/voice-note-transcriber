"""
Transcritor de Áudio de Zap — app Windows (single-file).

Drag & drop de arquivos de áudio → Whisper API → limpeza GPT opcional → texto na tela.
Tema claro/escuro automático (segue o Windows). Chave de API guardada no
Gerenciador de Credenciais do Windows (DPAPI) — nunca em arquivo de texto.
"""

import os
import sys
import json
import math
import zlib
import random
import threading
import datetime
import traceback
import webbrowser
from pathlib import Path

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import requests

# ─── pygame (áudio) ───────────────────────────────────────────────────────────
try:
    import pygame
    pygame.mixer.init()
    _PYGAME_OK = True
except Exception:
    _PYGAME_OK = False

# ─── mutagen (duração do áudio) ───────────────────────────────────────────────
try:
    import mutagen
    _MUTAGEN_OK = True
except Exception:
    _MUTAGEN_OK = False

# ─── pyogg (decode Opus→WAV para pygame) ──────────────────────────────────────
try:
    import pyogg
    _PYOGG_OK = bool(pyogg.PYOGG_OPUS_AVAIL)
except Exception:
    _PYOGG_OK = False


# ─── Configuração ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "appearance": "system",   # system | light | dark
    "ui_language": "auto",    # auto (Windows, fallback inglês) | pt | en | es
    "base_url": "https://api.openai.com/v1",
    "whisper_model": "whisper-1",
    "gpt_model": "gpt-4.1-mini",
    "language": "auto",       # auto = o Whisper detecta (padrão)
    "apply_cleanup": True,
    # Vazio = usar o prompt padrão do idioma corrente. Só vira texto quando o
    # usuário personaliza (ver effective_cleanup_prompt / is_custom_prompt).
    "cleanup_prompt": "",
}

# ─── Prompts de limpeza por idioma ────────────────────────────────────────────
#
# O prompt padrão acompanha o idioma (ver prompt_lang). Se o usuário editar o
# texto, a personalização vence e nada mais é trocado automaticamente.

CLEANUP_PROMPTS = {}

CLEANUP_PROMPTS["pt"] = """## Instruções para limpeza de transcrição (speech-to-text)

**CRÍTICO:** Sua única função é **limpar e formatar a transcrição**.
Nunca altere o sentido do texto, nunca acrescente conteúdo, nunca remova palavras relevantes e **nunca parafraseie**.

Mesmo que alguma palavra pareça incorreta, mantenha-a se houver dúvida.
Quando estiver em dúvida, preserve a formulação original.

Limpe a transcrição de fala para texto seguindo as regras abaixo.

---

## Regras

### 1. Correções ortográficas e pontuação

Corrija erros de ortografia, acentuação, uso de maiúsculas e pontuação.

Evite anacolutos. Tenha atenção às formas de falar dos cariocas (sotaque e expressões típicas), para não ficar esquisito na linguagem escrita.

Adicione pontuação quando estiver claramente ausente. Seja especialmente atento ao uso de vírgulas.

Considere estruturas formais da língua portuguesa, incluindo ordem inversa de sujeito e predicado, uso da partícula -se em verbos como postula-se, pleiteia-se, deseja-se, e concordância na voz passiva sintética.

Não reescreva frases — apenas corrija ortografia e pontuação.

### 2. Autocorreções do falante

Quando o próprio falante se corrige, mantenha apenas a versão final.
Padrões: "desculpa", "quer dizer", "na verdade", "não, espera", "pera", "melhor dizendo", "corrigindo".

### 3. Comandos de pontuação falados

Converta pontuação falada: ponto final → . | vírgula → , | interrogação → ? | exclamação → ! | dois pontos → : | abre/fecha aspas → " | abre/fecha parênteses → ()

### 4. Quebras de linha

Converta "nova linha" e "novo parágrafo". Insira parágrafos em mudanças claras de assunto.

### 5. Remoção de hesitações

Remova: hã, éé, ah, uh, hum, tipo (muleta), assim (vício), então (sem função), sabe, né.
Não remova quando tiverem significado real.

### 6. Números

Converta por extenso em dígitos. Em prosa, mantenha 1-12 por extenso.
Sempre dígitos: %, R$, medidas, listas, datas.
Não altere: anos, nomes próprios.

### 7. Listas

Formate como lista só quando o falante claramente enumera itens. Nunca transforme narrativa em lista.

---

## Restrições absolutas

Não: parafrasear, reescrever, reorganizar, adicionar, remover conteúdo relevante, traduzir, adicionar títulos.
Mantenha o idioma original.

## Retorno

Retorne **apenas a transcrição limpa**, sem comentários ou explicações.

## Transcrição

{transcricao}"""

CLEANUP_PROMPTS["en"] = """## Speech-to-text transcript cleanup instructions

**CRITICAL:** Your only job is to **clean up and format the transcript**.
Never change the meaning, never add content, never remove relevant words and **never paraphrase**.

Even if a word looks wrong, keep it when in doubt.
When uncertain, preserve the original wording.

Clean up the speech-to-text transcript following the rules below.

---

## Rules

### 1. Spelling and punctuation

Fix spelling, capitalisation and punctuation errors.

Add punctuation where it is clearly missing. Pay particular attention to commas.

Do not rewrite sentences — only fix spelling and punctuation.

### 2. Speaker self-corrections

When the speaker corrects themselves, keep only the final version.
Patterns: "sorry", "I mean", "actually", "no, wait", "let me rephrase".

### 3. Spoken punctuation commands

Convert spoken punctuation: period/full stop → . | comma → , | question mark → ? | exclamation mark → ! | colon → : | open/close quotes → " | open/close parenthesis → ()

### 4. Line breaks

Convert "new line" and "new paragraph". Add paragraph breaks at clear topic changes.

### 5. Filler removal

Remove: uh, um, er, hmm, "like" (as a crutch), "you know", "I mean" (when meaningless), "right" (as a tag).
Do not remove them when they carry real meaning.

### 6. Numbers

Convert spelled-out numbers to digits. In prose, keep 1-12 spelled out.
Always digits: %, currency, measurements, lists, dates.
Do not change: years, proper nouns.

### 7. Lists

Format as a list only when the speaker clearly enumerates items. Never turn narration into a list.

---

## Absolute restrictions

Do not: paraphrase, rewrite, reorganise, add, remove relevant content, translate, add headings.
Keep the original language.

## Output

Return **only the cleaned transcript**, with no comments or explanations.

## Transcript

{transcricao}"""

CLEANUP_PROMPTS["es"] = """## Instrucciones para limpiar una transcripción (voz a texto)

**CRÍTICO:** Tu única función es **limpiar y formatear la transcripción**.
Nunca cambies el sentido del texto, nunca agregues contenido, nunca elimines palabras relevantes y **nunca parafrasees**.

Aunque alguna palabra parezca incorrecta, consérvala si tienes dudas.
Ante la duda, preserva la formulación original.

Limpia la transcripción siguiendo las reglas de abajo.

---

## Reglas

### 1. Ortografía y puntuación

Corrige errores de ortografía, acentuación, mayúsculas y puntuación.

Agrega puntuación cuando falte claramente. Presta especial atención a las comas.

No reescribas frases — solo corrige ortografía y puntuación.

### 2. Autocorrecciones del hablante

Cuando el propio hablante se corrige, conserva solo la versión final.
Patrones: "perdón", "quiero decir", "en realidad", "no, espera", "mejor dicho".

### 3. Comandos de puntuación dictados

Convierte la puntuación dictada: punto → . | coma → , | signo de interrogación → ¿? | signo de exclamación → ¡! | dos puntos → : | abrir/cerrar comillas → " | abrir/cerrar paréntesis → ()

### 4. Saltos de línea

Convierte "nueva línea" y "nuevo párrafo". Inserta párrafos en cambios claros de tema.

### 5. Eliminación de muletillas

Elimina: eh, este, mmm, o sea (como muletilla), tipo, ¿viste?, ¿no?
No las elimines cuando tengan significado real.

### 6. Números

Convierte los números escritos con letras a dígitos. En prosa, mantén del 1 al 12 con letras.
Siempre en dígitos: %, moneda, medidas, listas, fechas.
No cambies: años, nombres propios.

### 7. Listas

Usa formato de lista solo cuando el hablante enumera claramente. Nunca conviertas una narración en lista.

---

## Restricciones absolutas

No: parafrasear, reescribir, reorganizar, agregar, eliminar contenido relevante, traducir, agregar títulos.
Mantén el idioma original.

## Salida

Devuelve **solo la transcripción limpia**, sin comentarios ni explicaciones.

## Transcripción

{transcricao}"""

CLEANUP_PROMPTS["fr"] = """## Instructions de nettoyage de transcription (reconnaissance vocale)

**CRITIQUE :** Votre seule fonction est de **nettoyer et formater la transcription**.
Ne changez jamais le sens, n'ajoutez jamais de contenu, ne supprimez jamais de mots pertinents et **ne paraphrasez jamais**.

Même si un mot semble incorrect, conservez-le en cas de doute.

Nettoyez la transcription en suivant les règles ci-dessous.

---

## Règles

### 1. Orthographe et ponctuation

Corrigez l'orthographe, les accents, les majuscules et la ponctuation.
Ajoutez la ponctuation manifestement absente, en particulier les virgules.
Ne réécrivez pas les phrases — corrigez seulement l'orthographe et la ponctuation.

### 2. Autocorrections du locuteur

Quand le locuteur se corrige, ne gardez que la version finale.
Motifs : « pardon », « je veux dire », « en fait », « non, attends ».

### 3. Ponctuation dictée

Convertissez la ponctuation dictée : point → . | virgule → , | point d'interrogation → ? | point d'exclamation → ! | deux-points → : | ouvrir/fermer les guillemets → " | ouvrir/fermer la parenthèse → ()

### 4. Sauts de ligne

Convertissez « nouvelle ligne » et « nouveau paragraphe ». Insérez des paragraphes aux changements clairs de sujet.

### 5. Suppression des hésitations

Supprimez : euh, hum, ben, genre (béquille), tu vois, quoi (en fin de phrase).
Ne les supprimez pas lorsqu'ils portent un sens réel.

### 6. Nombres

Convertissez les nombres écrits en toutes lettres en chiffres. En prose, gardez 1-12 en lettres.
Toujours en chiffres : %, monnaie, mesures, listes, dates.
Ne changez pas : les années, les noms propres.

### 7. Listes

Utilisez une liste seulement quand le locuteur énumère clairement. Ne transformez jamais un récit en liste.

---

## Restrictions absolues

Ne pas : paraphraser, réécrire, réorganiser, ajouter, supprimer du contenu pertinent, traduire, ajouter des titres.
Conservez la langue d'origine.

## Sortie

Renvoyez **uniquement la transcription nettoyée**, sans commentaire ni explication.

## Transcription

{transcricao}"""

CLEANUP_PROMPTS["de"] = """## Anweisungen zur Bereinigung einer Transkription (Sprache zu Text)

**KRITISCH:** Ihre einzige Aufgabe ist es, die **Transkription zu bereinigen und zu formatieren**.
Ändern Sie niemals den Sinn, fügen Sie niemals Inhalte hinzu, entfernen Sie niemals relevante Wörter und **paraphrasieren Sie niemals**.

Auch wenn ein Wort falsch erscheint, behalten Sie es im Zweifelsfall bei.

Bereinigen Sie die Transkription nach den folgenden Regeln.

---

## Regeln

### 1. Rechtschreibung und Zeichensetzung

Korrigieren Sie Rechtschreibung, Groß- und Kleinschreibung sowie Zeichensetzung.
Ergänzen Sie eindeutig fehlende Satzzeichen, besonders Kommas.
Formulieren Sie Sätze nicht um — korrigieren Sie nur Rechtschreibung und Zeichensetzung.

### 2. Selbstkorrekturen der sprechenden Person

Wenn die sprechende Person sich selbst korrigiert, behalten Sie nur die endgültige Fassung.
Muster: „Entschuldigung“, „ich meine“, „eigentlich“, „nein, warte“.

### 3. Diktierte Satzzeichen

Wandeln Sie diktierte Satzzeichen um: Punkt → . | Komma → , | Fragezeichen → ? | Ausrufezeichen → ! | Doppelpunkt → : | Anführungszeichen auf/zu → " | Klammer auf/zu → ()

### 4. Zeilenumbrüche

Wandeln Sie „neue Zeile“ und „neuer Absatz“ um. Setzen Sie Absätze bei klarem Themenwechsel.

### 5. Entfernen von Füllwörtern

Entfernen Sie: äh, ähm, hm, halt, also (ohne Funktion), ne, weißt du.
Entfernen Sie sie nicht, wenn sie eine echte Bedeutung tragen.

### 6. Zahlen

Wandeln Sie ausgeschriebene Zahlen in Ziffern um. Im Fließtext 1-12 ausgeschrieben lassen.
Immer Ziffern: %, Währung, Maße, Listen, Daten.
Nicht ändern: Jahreszahlen, Eigennamen.

### 7. Listen

Formatieren Sie nur dann als Liste, wenn eindeutig aufgezählt wird. Machen Sie aus einer Erzählung nie eine Liste.

---

## Absolute Einschränkungen

Nicht: paraphrasieren, umschreiben, umstellen, hinzufügen, relevante Inhalte entfernen, übersetzen, Überschriften ergänzen.
Behalten Sie die Originalsprache bei.

## Ausgabe

Geben Sie **nur die bereinigte Transkription** zurück, ohne Kommentare oder Erklärungen.

## Transkription

{transcricao}"""

CLEANUP_PROMPTS["it"] = """## Istruzioni per la pulizia di una trascrizione (da voce a testo)

**CRITICO:** La tua unica funzione è **pulire e formattare la trascrizione**.
Non alterare mai il senso, non aggiungere mai contenuti, non rimuovere mai parole rilevanti e **non parafrasare mai**.

Anche se una parola sembra sbagliata, mantienila in caso di dubbio.

Pulisci la trascrizione seguendo le regole riportate sotto.

---

## Regole

### 1. Ortografia e punteggiatura

Correggi errori di ortografia, accenti, maiuscole e punteggiatura.
Aggiungi la punteggiatura chiaramente mancante, con particolare attenzione alle virgole.
Non riscrivere le frasi — correggi solo ortografia e punteggiatura.

### 2. Autocorrezioni di chi parla

Quando chi parla si corregge, mantieni solo la versione finale.
Schemi: «scusa», «cioè», «in realtà», «no, aspetta».

### 3. Punteggiatura dettata

Converti la punteggiatura dettata: punto → . | virgola → , | punto interrogativo → ? | punto esclamativo → ! | due punti → : | apri/chiudi virgolette → " | apri/chiudi parentesi → ()

### 4. Interruzioni di riga

Converti «a capo» e «nuovo paragrafo». Inserisci paragrafi ai cambi di argomento evidenti.

### 5. Rimozione delle esitazioni

Rimuovi: eh, ehm, mmm, tipo (riempitivo), cioè (senza funzione), no?, sai.
Non rimuoverli quando hanno un significato reale.

### 6. Numeri

Converti in cifre i numeri scritti a lettere. In prosa mantieni 1-12 a lettere.
Sempre in cifre: %, valuta, misure, elenchi, date.
Non modificare: anni, nomi propri.

### 7. Elenchi

Usa il formato elenco solo quando chi parla enumera chiaramente. Non trasformare mai una narrazione in elenco.

---

## Restrizioni assolute

Non: parafrasare, riscrivere, riorganizzare, aggiungere, rimuovere contenuti rilevanti, tradurre, aggiungere titoli.
Mantieni la lingua originale.

## Output

Restituisci **solo la trascrizione pulita**, senza commenti né spiegazioni.

## Trascrizione

{transcricao}"""

CLEANUP_PROMPTS["ja"] = """## 文字起こし（音声認識）のクリーンアップ指示

**重要:** あなたの唯一の役割は、**文字起こしを整形・清書すること**です。
意味を変えない、内容を追加しない、重要な語を削除しない、そして**言い換えは絶対にしない**でください。

誤りに見える語でも、迷う場合はそのまま残してください。

以下の規則に従って文字起こしを整えてください。

---

## 規則

### 1. 表記と句読点

誤字・表記ゆれ・句読点の誤りを修正します。
明らかに欠けている句読点を補います。
文を書き直さず、表記と句読点のみ修正してください。

### 2. 話者による言い直し

話者が自分で言い直した場合は、最終版のみを残します。
例:「すみません」「というか」「実は」「いや、待って」。

### 3. 音声による句読点指示

読み上げられた句読点を変換します: 句点 → 。| 読点 → 、| 疑問符 → ? | 感嘆符 → ! | かぎ括弧の開閉 → 「」| 丸括弧の開閉 → （）

### 4. 改行

「改行」「新しい段落」を変換します。話題が明確に変わる箇所で段落を分けます。

### 5. フィラーの削除

削除する語: えー、あの、ええと、まあ（意味のない場合）、なんか、そのー。
実際の意味を持つ場合は削除しないでください。

### 6. 数値

読み上げられた数を算用数字にします。
必ず算用数字にするもの: %、金額、寸法、箇条書き、日付。
変更しないもの: 年号、固有名詞。

### 7. 箇条書き

話者が明確に列挙している場合のみ箇条書きにします。語りを箇条書きに変えないでください。

---

## 絶対的な制約

してはいけないこと: 言い換え、書き直し、並べ替え、追加、重要な内容の削除、翻訳、見出しの追加。
元の言語を維持してください。

## 出力

**整形済みの文字起こしのみ**を返してください。コメントや説明は不要です。

## 文字起こし

{transcricao}"""

CLEANUP_PROMPTS["zh"] = """## 语音转文字稿整理说明

**关键:** 你唯一的任务是**整理并排版这份文字稿**。
不得改变原意、不得添加内容、不得删除相关词语，**绝不可改写措辞**。

即使某个词看起来有误，若不确定请保留原样。

请按以下规则整理文字稿。

---

## 规则

### 1. 用字与标点

修正错别字、大小写与标点错误。
补上明显缺失的标点，尤其注意逗号。
不要重写句子——只修正用字与标点。

### 2. 说话者的自我更正

说话者自我更正时，只保留最终版本。
常见说法:「不好意思」「我是说」「其实」「不对，等一下」。

### 3. 口述的标点指令

转换口述标点: 句号 → 。| 逗号 → ，| 问号 → ？| 感叹号 → ！| 冒号 → ： | 引号开合 → 「」| 括号开合 → （）

### 4. 换行

转换「换行」和「另起一段」。在话题明显转换处分段。

### 5. 删除语气词

删除: 嗯、呃、那个、就是（口头禅）、然后（无实义）、你知道吧。
若这些词具有实际意义，则不要删除。

### 6. 数字

将口述数字转为阿拉伯数字。
一律使用数字的情况: %、金额、度量、列表、日期。
不要改动: 年份、专有名词。

### 7. 列表

只有当说话者明确列举时才排成列表。绝不要把叙述改成列表。

---

## 绝对限制

不得: 改写、重写、重新组织、添加、删除相关内容、翻译、添加标题。
保持原文语言。

## 输出

只返回**整理后的文字稿**，不要任何评论或说明。

## 文字稿

{transcricao}"""


def prompt_lang(cfg: dict) -> str:
    """Idioma do prompt padrão.

    Segue o idioma da UI. Quando o áudio está fixado num idioma que a UI não
    cobre (fr, de, it, ja, zh), esse idioma vence — é o idioma do texto que o
    prompt vai limpar.
    """
    audio = cfg.get("language", "auto")
    if audio in CLEANUP_PROMPTS and audio not in ("pt", "en", "es"):
        return audio
    return UI_LANG if UI_LANG in CLEANUP_PROMPTS else "en"


def default_cleanup_prompt(cfg: dict) -> str:
    return CLEANUP_PROMPTS[prompt_lang(cfg)]


def is_custom_prompt(text: str) -> bool:
    """Texto personalizado = diferente de todos os prompts padrão."""
    t = (text or "").strip()
    return bool(t) and all(t != p.strip() for p in CLEANUP_PROMPTS.values())


def effective_cleanup_prompt(cfg: dict) -> str:
    """Prompt em uso: o personalizado, se houver; senão o padrão do idioma."""
    saved = cfg.get("cleanup_prompt", "")
    return saved if is_custom_prompt(saved) else default_cleanup_prompt(cfg)


CONFIG_FILE = Path(os.getenv("APPDATA", ".")) / "TranscricaoApp" / "config.json"


def load_config():
    """Carrega config do disco.

    Retorna (cfg, legacy_key, scrubbed):
    - legacy_key: chave de API encontrada num config antigo (usada só em memória);
    - scrubbed: True se o arquivo continha "api_key" e foi regravado sem ela.
    """
    legacy_key = ""
    scrubbed = False
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if "api_key" in loaded:
                legacy_key = str(loaded.pop("api_key") or "").strip()
                scrubbed = True
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(loaded)
            cfg.pop("api_key", None)
            if scrubbed:
                try:
                    save_config(cfg)  # regrava imediatamente sem a chave
                except Exception:
                    pass
        except Exception:
            cfg = DEFAULT_CONFIG.copy()
    return cfg, legacy_key, scrubbed


def save_config(cfg: dict):
    """Grava a configuração em disco. A chave de API NUNCA vai para o JSON
    (ela mora no Gerenciador de Credenciais do Windows — ver seção Cofre)."""
    data = dict(cfg)
    data.pop("api_key", None)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Cofre da chave (Gerenciador de Credenciais do Windows) ──────────────────
#
# A chave NÃO fica em config.json (texto plano legível por qualquer processo).
# Usamos o Credential Manager via ctypes/advapi32: cifrado com DPAPI pela conta
# do Windows — só abre nesta conta, nesta máquina, e aparece para o usuário em
# Painel de Controle → Gerenciador de Credenciais → Credenciais Genéricas.

CRED_TARGET = "TranscritorDeAudio/OpenAI"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2

if os.name == "nt":
    import ctypes
    import ctypes.wintypes as _wt

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", _wt.DWORD),
            ("Type", _wt.DWORD),
            ("TargetName", _wt.LPWSTR),
            ("Comment", _wt.LPWSTR),
            ("LastWritten", _wt.FILETIME),
            ("CredentialBlobSize", _wt.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", _wt.DWORD),
            ("AttributeCount", _wt.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", _wt.LPWSTR),
            ("UserName", _wt.LPWSTR),
        ]

    _advapi32 = ctypes.windll.advapi32


def vault_read() -> str:
    """Lê a chave do Gerenciador de Credenciais. '' se não existir."""
    if os.name != "nt":
        return ""
    try:
        pcred = ctypes.POINTER(_CREDENTIAL)()
        ok = _advapi32.CredReadW(CRED_TARGET, _CRED_TYPE_GENERIC, 0,
                                 ctypes.byref(pcred))
        if not ok:
            return ""
        try:
            cred = pcred.contents
            if not cred.CredentialBlobSize:
                return ""
            raw = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
            return raw.decode("utf-16-le").strip()
        finally:
            _advapi32.CredFree(pcred)
    except Exception:
        return ""


def vault_write(key: str) -> bool:
    """Grava a chave no Gerenciador de Credenciais (sobrescreve se existir)."""
    if os.name != "nt" or not key.strip():
        return False
    try:
        blob = key.strip().encode("utf-16-le")
        buf = ctypes.create_string_buffer(blob, len(blob))
        cred = _CREDENTIAL()
        cred.Flags = 0
        cred.Type = _CRED_TYPE_GENERIC
        cred.TargetName = CRED_TARGET
        cred.Comment = "Chave da API OpenAI usada pelo Transcritor de Áudio"
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))
        cred.Persist = _CRED_PERSIST_LOCAL_MACHINE
        cred.UserName = "openai"
        return bool(_advapi32.CredWriteW(ctypes.byref(cred), 0))
    except Exception:
        return False


def vault_delete() -> bool:
    """Remove a chave do Gerenciador de Credenciais."""
    if os.name != "nt":
        return False
    try:
        return bool(_advapi32.CredDeleteW(CRED_TARGET, _CRED_TYPE_GENERIC, 0))
    except Exception:
        return False


# ─── Lógica de transcrição ────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".ogg", ".oga", ".opus",
                        ".wav", ".webm", ".flac"}

MIME_TYPES = {
    ".mp3":  "audio/mpeg",
    ".mp4":  "audio/mp4",
    ".m4a":  "audio/mp4",
    ".ogg":  "audio/ogg",
    ".oga":  "audio/ogg",
    ".opus": "audio/ogg",
    ".wav":  "audio/wav",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
}

WHISPER_MODELS = ["whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
GPT_MODELS = ["gpt-4.1-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini"]
LANGUAGES = ["pt", "en", "es", "fr", "de", "it", "ja", "zh", "auto"]

# Formatos com seek confiável via pygame
SEEK_SUPPORTED = {".mp3", ".ogg", ".oga", ".opus", ".wav"}

# Formatos que precisam conversão prévia para WAV (Opus não é suportado pelo SDL2)
NEEDS_CONVERSION = {".ogg", ".oga", ".opus"}

DEFAULT_BASE_URL = "https://api.openai.com/v1"


def api_base(cfg: dict) -> str:
    """Endpoint da API: OpenAI por padrão; aceita qualquer compatível com v1."""
    base = (cfg.get("base_url") or "").strip().rstrip("/")
    return base or DEFAULT_BASE_URL


def is_insecure_endpoint(url: str) -> bool:
    """True para http:// fora de localhost — a chave viajaria em texto claro."""
    u = (url or "").strip().lower()
    if not u.startswith("http://"):
        return False
    host = u[len("http://"):].split("/")[0].split(":")[0]
    return host not in ("localhost", "127.0.0.1", "::1", "[::1]")


# ─── Idioma da interface (pt / en / es) ───────────────────────────────────────
#
# Default "auto": idioma de exibição do Windows, com fallback para inglês.
# O log permanece técnico (pt) — só a UI é traduzida.

UI_LANG = "pt"  # resolvido no boot do App

# Cada idioma escrito no próprio idioma — a lista não muda com a UI.
UI_LANGUAGES = ["auto", "pt", "en", "es"]
UI_LANG_NAMES = {
    "auto": "Auto (Windows)",
    "pt": "Português",
    "en": "English",
    "es": "Español",
}

# key: (pt-BR, en, es-419)
I18N = {
    "drop_title":        ("Solte o áudio aqui", "Drop your audio here", "Suelta el audio aquí"),
    "drop_sub":          ("ou clique para escolher — vários de uma vez",
                          "or click to choose — several at once",
                          "o haz clic para elegir — varios a la vez"),
    "drop_more":         ("Solte mais áudios aqui — ou clique",
                          "Drop more audio here — or click",
                          "Suelta más audios aquí — o haz clic"),
    "nav_settings":      ("ajustes", "settings", "ajustes"),
    "nav_log":           ("log", "log", "registro"),
    "status_ready":      ("● pronto", "● ready", "● listo"),
    "status_processing": ("● processando…", "● processing…", "● procesando…"),
    "status_no_key":     ("● falta a chave", "● missing key", "● falta la clave"),
    "theme_system":      ("◐ auto", "◐ auto", "◐ auto"),
    "theme_light":       ("○ claro", "○ light", "○ claro"),
    "theme_dark":        ("● escuro", "● dark", "● oscuro"),
    "transcribe":        ("Transcrever", "Transcribe", "Transcribir"),
    "queued":            ("na fila…", "queued…", "en la fila…"),
    "sending_whisper":   ("enviando ao Whisper…", "sending to Whisper…", "enviando a Whisper…"),
    "cleaning_gpt":      ("limpando com GPT…", "cleaning up with GPT…", "limpiando con GPT…"),
    "copy":              ("Copiar", "Copy", "Copiar"),
    "copied":            ("Copiado", "Copied", "Copiado"),
    "save_txt":          ("Salvar .txt", "Save .txt", "Guardar .txt"),
    "saved":             ("Salvo", "Saved", "Guardado"),
    "rewrite":           ("Reescrever", "Rewrite", "Reescribir"),
    "close":             ("Fechar", "Close", "Cerrar"),
    "send":              ("Enviar", "Send", "Enviar"),
    "rewrite_ph":        ('Ex.: "resuma", "escreva em inglês", "liste os pontos principais"',
                          'E.g.: "summarize", "translate to Portuguese", "list the key points"',
                          'Ej.: "resume", "escribe en inglés", "lista los puntos principales"'),
    "rewrite_no_text":   ("Sem texto para reescrever.", "No text to rewrite.", "No hay texto para reescribir."),
    "rewrite_no_key":    ("Informe a chave de API em Ajustes.",
                          "Enter your API key in Settings.",
                          "Ingresa la clave de API en Ajustes."),
    "rewrite_sending":   ("Enviando para o GPT...", "Sending to GPT...", "Enviando a GPT..."),
    "rewrite_done":      ("Texto reescrito.", "Text rewritten.", "Texto reescrito."),
    "failed":            ("falha na transcrição", "transcription failed", "falló la transcripción"),
    "characters":        ("caracteres", "characters", "caracteres"),
    "copy_all":          ("Copiar tudo", "Copy all", "Copiar todo"),
    "clear_all":         ("Limpar tudo", "Clear all", "Limpiar todo"),
    "txt_file":          ("Arquivo de texto", "Text file", "Archivo de texto"),
    "sec_api":           ("API", "API", "API"),
    "sec_transcription": ("Transcrição", "Transcription", "Transcripción"),
    "sec_cleanup":       ("Limpeza GPT", "GPT cleanup", "Limpieza GPT"),
    "sec_interface":     ("Interface", "Interface", "Interfaz"),
    "lbl_key":           ("Chave da OpenAI", "OpenAI API key", "Clave de OpenAI"),
    "show":              ("mostrar", "show", "mostrar"),
    "hide":              ("ocultar", "hide", "ocultar"),
    "key_hint":          ("Salva no Gerenciador de Credenciais do Windows — cifrada pela sua conta.",
                          "Stored in Windows Credential Manager — encrypted with your account.",
                          "Guardada en el Administrador de credenciales de Windows — cifrada con tu cuenta."),
    "test_key":          ("Testar chave", "Test key", "Probar clave"),
    "testing":           ("testando…", "testing…", "probando…"),
    "forget_key":        ("Esquecer chave", "Forget key", "Olvidar clave"),
    "key_removed":       ("chave removida do Gerenciador de Credenciais",
                          "key removed from Credential Manager",
                          "clave eliminada del Administrador de credenciales"),
    "lbl_endpoint":      ("Endpoint", "Endpoint", "Endpoint"),
    "endpoint_hint":     ("Qualquer API compatível com OpenAI v1 — deixe vazio para usar a OpenAI.",
                          "Any OpenAI v1-compatible API — leave empty to use OpenAI.",
                          "Cualquier API compatible con OpenAI v1 — déjalo vacío para usar OpenAI."),
    "endpoint_insecure": ("Endpoint sem HTTPS: sua chave seria enviada em texto claro.",
                          "Endpoint without HTTPS: your key would be sent in clear text.",
                          "Endpoint sin HTTPS: tu clave se enviaría en texto plano."),
    "lbl_whisper":       ("Modelo Whisper", "Whisper model", "Modelo Whisper"),
    "lbl_audio_lang":    ("Idioma do áudio", "Audio language", "Idioma del audio"),
    "lbl_cleanup":       ("Aplicar limpeza", "Apply cleanup", "Aplicar limpieza"),
    "lbl_gpt":           ("Modelo GPT", "GPT model", "Modelo GPT"),
    "lbl_ui_lang":       ("Idioma da interface", "Interface language", "Idioma de la interfaz"),
    "prompt_toggle":     ("Prompt de limpeza", "Cleanup prompt", "Prompt de limpieza"),
    "prompt_var":        ("Variável disponível: {transcricao}",
                          "Available variable: {transcricao}",
                          "Variable disponible: {transcricao}"),
    "prompt_default":    ("prompt padrão ({lang}) — acompanha o idioma",
                          "default prompt ({lang}) — follows the language",
                          "prompt predeterminado ({lang}) — sigue el idioma"),
    "prompt_custom":     ("prompt personalizado — não muda com o idioma",
                          "custom prompt — does not change with the language",
                          "prompt personalizado — no cambia con el idioma"),
    "restore_prompt":    ("Restaurar padrão", "Restore default", "Restaurar predeterminado"),
    "save_settings":     ("Salvar configurações", "Save settings", "Guardar configuración"),
    "settings_saved":    ("Configurações salvas.", "Settings saved.", "Configuración guardada."),
    "settings_saved_key": ("Configurações salvas (chave no Gerenciador de Credenciais).",
                           "Settings saved (key in Credential Manager).",
                           "Configuración guardada (clave en el Administrador de credenciales)."),
    "ui_lang_restart":   ("Salvo — reinicie o aplicativo para aplicar o idioma.",
                          "Saved — restart the app to apply the language.",
                          "Guardado — reinicia la aplicación para aplicar el idioma."),
    "test_enter_first":  ("informe a chave antes de testar",
                          "enter the key before testing",
                          "ingresa la clave antes de probar"),
    "test_checking":     ("consultando {base}/models …", "checking {base}/models …", "consultando {base}/models …"),
    "test_valid":        ("✓ chave válida — {n} modelos disponíveis",
                          "✓ key valid — {n} models available",
                          "✓ clave válida — {n} modelos disponibles"),
    "test_valid_simple": ("✓ chave válida", "✓ key valid", "✓ clave válida"),
    "test_invalid":      ("✗ chave inválida (HTTP 401)", "✗ invalid key (HTTP 401)", "✗ clave inválida (HTTP 401)"),
    "test_timeout":      ("✗ timeout — o endpoint não respondeu",
                          "✗ timeout — the endpoint did not respond",
                          "✗ timeout — el endpoint no respondió"),
    "test_noconn":       ("✗ sem conexão com o endpoint",
                          "✗ no connection to the endpoint",
                          "✗ sin conexión con el endpoint"),
    "log_title":         ("Log de execução", "Execution log", "Registro de ejecución"),
    "clear":             ("Limpar", "Clear", "Limpiar"),
    "one_file":          ("{name}  ({mb} MB)", "{name}  ({mb} MB)", "{name}  ({mb} MB)"),
    "n_files":           ("{n} arquivos selecionados  ({mb} MB no total)",
                          "{n} files selected  ({mb} MB total)",
                          "{n} archivos seleccionados  ({mb} MB en total)"),
    "no_valid_title":    ("Nenhum arquivo válido", "No valid files", "Ningún archivo válido"),
    "no_valid_body":     ("Nenhum dos arquivos selecionados tem formato suportado.",
                          "None of the selected files has a supported format.",
                          "Ninguno de los archivos seleccionados tiene un formato compatible."),
    "key_missing_title": ("Chave de API pendente", "API key missing", "Falta la clave de API"),
    "key_missing_body":  ("Informe sua chave da OpenAI na aba Ajustes.\nEla fica guardada no Gerenciador de Credenciais do Windows.",
                          "Enter your OpenAI API key in Settings.\nIt is stored in Windows Credential Manager.",
                          "Ingresa tu clave de OpenAI en Ajustes.\nSe guarda en el Administrador de credenciales de Windows."),
    "audio_files":       ("Arquivos de áudio", "Audio files", "Archivos de audio"),
    "all_files":         ("Todos os arquivos", "All files", "Todos los archivos"),
    "audio_na_title":    ("Áudio indisponível", "Audio unavailable", "Audio no disponible"),
    "audio_na_body":     ("pygame não está disponível.", "pygame is not available.", "pygame no está disponible."),
    "audio_load_error":  ("Erro ao carregar áudio", "Error loading audio", "Error al cargar el audio"),
    "err_no_key":        ("Chave de API não informada. Vá em Ajustes.",
                          "API key not set. Open Settings.",
                          "Clave de API no ingresada. Ve a Ajustes."),
    "err_too_big":       ("Arquivo muito grande: {mb} MB. A API do Whisper aceita no máximo 25 MB.",
                          "File too large: {mb} MB. The Whisper API accepts at most 25 MB.",
                          "Archivo demasiado grande: {mb} MB. La API de Whisper acepta como máximo 25 MB."),
    "err_no_conn":       ("Sem conexão com a internet ou endpoint inacessível.",
                          "No internet connection, or the endpoint is unreachable.",
                          "Sin conexión a internet o endpoint inaccesible."),
    "err_timeout":       ("Timeout: a API não respondeu em 5 minutos.",
                          "Timeout: the API did not respond within 5 minutes.",
                          "Timeout: la API no respondió en 5 minutos."),
    "footer_offer":      ("transcritor de áudio de zap é um oferecimento de",
                          "transcritor de áudio de zap is brought to you by",
                          "transcritor de áudio de zap es un obsequio de"),
    # O nome é um trocadilho brasileiro ("zap" = WhatsApp): fora do pt-BR,
    # uma linha discreta explica o que a ferramenta faz.
    "wordmark_aka":      ("",
                          "a.k.a. WhatsApp voice note transcriber",
                          "a.k.a. transcriptor de notas de voz de WhatsApp"),
}


def tr(key: str, **fmt) -> str:
    pt, en, es = I18N[key]
    s = {"pt": pt, "en": en, "es": es}.get(UI_LANG, en)
    return s.format(**fmt) if fmt else s


def _detect_windows_ui_lang() -> str:
    """Idioma de exibição do Windows → pt/en/es, com fallback para inglês."""
    try:
        import locale as _locale
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        code = (_locale.windows_locale.get(lcid) or "en").lower()
    except Exception:
        code = "en"
    if code.startswith("pt"):
        return "pt"
    if code.startswith("es"):
        return "es"
    return "en"


def resolve_ui_lang(cfg: dict) -> str:
    choice = cfg.get("ui_language", "auto")
    if choice in ("pt", "en", "es"):
        return choice
    return _detect_windows_ui_lang()


def _detect_windows_audio_lang() -> str:
    """Idioma presumido do áudio = idioma do Windows, se o Whisper o suportar."""
    try:
        import locale as _locale
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        code = (_locale.windows_locale.get(lcid) or "en").lower().split("_")[0]
    except Exception:
        code = "en"
    return code if code in LANGUAGES else "en"


def transcribe_audio(file_path: str, cfg: dict, api_key: str,
                     progress_cb=None, log_cb=None) -> str:
    """Envia o áudio ao Whisper e, opcionalmente, aplica a limpeza via GPT."""
    def log(msg):
        if log_cb:
            log_cb(msg)

    api_key = (api_key or "").strip()
    if not api_key:
        raise ValueError(tr("err_no_key"))

    p = Path(file_path)
    ext = p.suffix.lower()
    mime = MIME_TYPES.get(ext, "application/octet-stream")
    file_size_mb = p.stat().st_size / (1024 * 1024)

    log(f"Arquivo: {p.name}")
    log(f"Tamanho: {file_size_mb:.1f} MB | Formato: {ext} | MIME: {mime}")
    log(f"Modelo Whisper: {cfg['whisper_model']} | Idioma: {cfg['language']}")

    if file_size_mb > 25:
        raise ValueError(tr("err_too_big", mb=f"{file_size_mb:.1f}"))

    headers = {"Authorization": f"Bearer {api_key}"}
    base = api_base(cfg)
    if base != DEFAULT_BASE_URL:
        log(f"Endpoint personalizado: {base}")

    if progress_cb:
        progress_cb(tr("sending_whisper"))
    log(f"POST {base}/audio/transcriptions ...")

    with open(file_path, "rb") as f:
        files = {"file": (p.name, f, mime)}
        data = {"model": cfg["whisper_model"], "response_format": "text"}
        if cfg["language"] != "auto":
            data["language"] = cfg["language"]

        resp = requests.post(
            f"{base}/audio/transcriptions",
            headers=headers, files=files, data=data, timeout=300
        )

    log(f"Whisper → HTTP {resp.status_code}")
    if not resp.ok:
        log(f"Corpo do erro: {resp.text[:800]}")
        raise RuntimeError(f"Erro Whisper (HTTP {resp.status_code}):\n{resp.text}")

    transcricao = resp.text.strip()
    log(f"Transcrição recebida: {len(transcricao)} caracteres")

    if not cfg.get("apply_cleanup"):
        log("Limpeza GPT desativada.")
        return transcricao

    if progress_cb:
        progress_cb(tr("cleaning_gpt"))
    log(f"POST {base}/chat/completions ({cfg['gpt_model']}) ...")

    prompt = effective_cleanup_prompt(cfg).replace("{transcricao}", transcricao)
    payload = {
        "model": cfg["gpt_model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    resp2 = requests.post(
        f"{base}/chat/completions",
        headers={**headers, "Content-Type": "application/json"},
        json=payload, timeout=300
    )

    log(f"GPT → HTTP {resp2.status_code}")
    if not resp2.ok:
        log(f"Corpo do erro: {resp2.text[:800]}")
        raise RuntimeError(f"Erro GPT (HTTP {resp2.status_code}):\n{resp2.text}")

    resultado = resp2.json()["choices"][0]["message"]["content"].strip()
    log(f"Limpeza concluída: {len(resultado)} caracteres")
    return resultado


# ─── Paleta (light, dark) ─────────────────────────────────────────────────────

ctk.set_appearance_mode("system")   # segue o tema do Windows, reage ao vivo
ctk.set_default_color_theme("blue")

# Estúdio de gravação: grafite neutro + âmbar de VU/fita como única cor viva.
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
WAVE_IDLE    = ("#c9ccd2", "#383d44")   # barras de onda ainda não tocadas


def _pick(color_tuple):
    """Resolve uma tupla (light, dark) para a cor do modo atual (uso em tk.Canvas)."""
    return color_tuple[1] if ctk.get_appearance_mode() == "Dark" else color_tuple[0]


# Tema manual: cicla auto → claro → escuro (persistido em config.json)
_THEME_ORDER = ["system", "light", "dark"]


def _theme_label(mode: str) -> str:
    return tr({"system": "theme_system", "light": "theme_light",
               "dark": "theme_dark"}.get(mode, "theme_system"))


def _apply_titlebar_theme(window):
    """Barra de título do Windows acompanha o tema (DWMWA 20, Win10 20H1+)."""
    if os.name != "nt":
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        val = ctypes.c_int(1 if ctk.get_appearance_mode() == "Dark" else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20,
                                                   ctypes.byref(val), 4)
    except Exception:
        pass


# ─── Fontes ───────────────────────────────────────────────────────────────────

# Três camadas de tipo: Display (wordmark/títulos), Text (conteúdo),
# Mono (dados e chrome — tempos, contadores, status, navegação).
UI_FAMILY = "Segoe UI"
DISPLAY_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"


def _detect_fonts(root):
    """Prefere as Segoe UI Variable (Win11) e Cascadia Mono, com fallback."""
    global UI_FAMILY, DISPLAY_FAMILY, MONO_FAMILY
    try:
        import tkinter.font as tkfont
        fams = set(tkfont.families(root))
        if "Segoe UI Variable Text" in fams:
            UI_FAMILY = "Segoe UI Variable Text"
        if "Segoe UI Variable Display" in fams:
            DISPLAY_FAMILY = "Segoe UI Variable Display"
        if "Cascadia Mono" in fams:
            MONO_FAMILY = "Cascadia Mono"
    except Exception:
        pass


def ui_font(size=13, weight="normal"):
    return ctk.CTkFont(family=UI_FAMILY, size=size, weight=weight)


def display_font(size=17, weight="bold"):
    return ctk.CTkFont(family=DISPLAY_FAMILY, size=size, weight=weight)


def mono_font(size=11):
    return ctk.CTkFont(family=MONO_FAMILY, size=size)


# ─── Helpers de botão ─────────────────────────────────────────────────────────

def primary_button(master, text, command, width=140, height=32):
    return ctk.CTkButton(
        master, text=text, command=command, width=width, height=height,
        corner_radius=8, font=ui_font(13, "bold"),
        fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT
    )


def ghost_button(master, text, command, width=110, height=32):
    return ctk.CTkButton(
        master, text=text, command=command, width=width, height=height,
        corner_radius=8, font=ui_font(13),
        fg_color="transparent", hover_color=SURFACE2,
        border_color=BORDER, border_width=1, text_color=TEXT
    )


# ─── Dropdown com chevron suave ───────────────────────────────────────────────
#
# O CTkOptionMenu desenha a seta em canvas e ela sai serrilhada. Aqui o chevron
# é renderizado via PIL em 8x e reduzido com LANCZOS (anti-aliasing real),
# num CTkImage com variante para cada tema.

_chevron_cache = {}


def _chevron_image(size=13):
    if size in _chevron_cache:
        return _chevron_cache[size]
    from PIL import Image, ImageDraw

    def render(color):
        s = size * 8
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        w = max(6, s // 8)
        pts = [(s * 0.22, s * 0.38), (s * 0.50, s * 0.66), (s * 0.78, s * 0.38)]
        d.line(pts, fill=color, width=w, joint="curve")
        r = w / 2
        for x, y in (pts[0], pts[2]):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)
        return img.resize((size, size), Image.LANCZOS)

    _chevron_cache[size] = ctk.CTkImage(
        light_image=render((25, 26, 28, 255)),      # TEXT no tema claro
        dark_image=render((242, 243, 245, 255)),    # TEXT no tema escuro
        size=(size, size)
    )
    return _chevron_cache[size]


_plus_cache = {}


def _plus_badge(size=52):
    """Disco âmbar pastel com um '+' — o convite para adicionar áudio."""
    if size in _plus_cache:
        return _plus_cache[size]
    from PIL import Image, ImageDraw

    def render(disc, stroke):
        s = size * 8
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([0, 0, s - 1, s - 1], fill=disc)
        arm, w = s * 0.24, s * 0.075
        c = s / 2
        d.rounded_rectangle([c - w / 2, c - arm, c + w / 2, c + arm],
                            radius=w / 2, fill=stroke)
        d.rounded_rectangle([c - arm, c - w / 2, c + arm, c + w / 2],
                            radius=w / 2, fill=stroke)
        return img.resize((size, size), Image.LANCZOS)

    _plus_cache[size] = ctk.CTkImage(
        light_image=render((253, 234, 205, 255), (178, 94, 9, 255)),
        dark_image=render((58, 42, 18, 255), (245, 165, 36, 255)),
        size=(size, size)
    )
    return _plus_cache[size]


GITHUB_URL = "https://github.com/ffapd1989"

# Marca oficial do GitHub (Octocat) como path SVG. Rasterizada aqui mesmo:
# achatamos as Béziers e preenchemos o polígono em 8x, reduzindo com LANCZOS —
# fica nítida em qualquer DPI e não exige nenhuma biblioteca de SVG.
GITHUB_PATH = (
    "M94,7399 C99.523,7399 104,7403.59 104,7409.253 C104,7413.782 101.138,"
    "7417.624 97.167,7418.981 C96.66,7419.082 96.48,7418.762 96.48,7418.489 "
    "C96.48,7418.151 96.492,7417.047 96.492,7415.675 C96.492,7414.719 96.172,"
    "7414.095 95.813,7413.777 C98.04,7413.523 100.38,7412.656 100.38,7408.718 "
    "C100.38,7407.598 99.992,7406.684 99.35,7405.966 C99.454,7405.707 99.797,"
    "7404.664 99.252,7403.252 C99.252,7403.252 98.414,7402.977 96.505,7404.303 "
    "C95.706,7404.076 94.85,7403.962 94,7403.958 C93.15,7403.962 92.295,"
    "7404.076 91.497,7404.303 C89.586,7402.977 88.746,7403.252 88.746,7403.252 "
    "C88.203,7404.664 88.546,7405.707 88.649,7405.966 C88.01,7406.684 87.619,"
    "7407.598 87.619,7408.718 C87.619,7412.646 89.954,7413.526 92.175,7413.785 "
    "C91.889,7414.041 91.63,7414.493 91.54,7415.156 C90.97,7415.418 89.522,"
    "7415.871 88.63,7414.304 C88.63,7414.304 88.101,7413.319 87.097,7413.247 "
    "C87.097,7413.247 86.122,7413.234 87.029,7413.87 C87.029,7413.87 87.684,"
    "7414.185 88.139,7415.37 C88.139,7415.37 88.726,7417.2 91.508,7416.58 "
    "C91.513,7417.437 91.522,7418.245 91.522,7418.489 C91.522,7418.76 91.338,"
    "7419.077 90.839,7418.982 C86.865,7417.627 84,7413.783 84,7409.253 "
    "C84,7403.59 88.478,7399 94,7399"
)


def _svg_path_points(d: str, steps: int = 18):
    """Achata um path SVG (M/L/C absolutos) numa lista de pontos."""
    import re
    tokens = re.findall(r"[MmLlCcZz]|-?\d*\.?\d+", d)
    pts, i, cur, start, cmd = [], 0, (0.0, 0.0), (0.0, 0.0), "M"
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                pts.append(start)
                continue
        if cmd in "Mm":
            cur = (float(tokens[i]), float(tokens[i + 1]))
            start = cur
            pts.append(cur)
            i += 2
            cmd = "L" if cmd == "M" else "l"
        elif cmd in "Ll":
            cur = (float(tokens[i]), float(tokens[i + 1]))
            pts.append(cur)
            i += 2
        elif cmd in "Cc":
            x0, y0 = cur
            c1 = (float(tokens[i]), float(tokens[i + 1]))
            c2 = (float(tokens[i + 2]), float(tokens[i + 3]))
            end = (float(tokens[i + 4]), float(tokens[i + 5]))
            for s in range(1, steps + 1):
                u = s / steps
                m = 1 - u
                pts.append((
                    m ** 3 * x0 + 3 * m * m * u * c1[0] + 3 * m * u * u * c2[0] + u ** 3 * end[0],
                    m ** 3 * y0 + 3 * m * m * u * c1[1] + 3 * m * u * u * c2[1] + u ** 3 * end[1],
                ))
            cur = end
            i += 6
        else:
            i += 1
    return pts


_github_cache = None


def _github_image(size=16):
    """Marca oficial do GitHub, rasterizada em 8x e reduzida com LANCZOS."""
    global _github_cache
    if _github_cache is not None:
        return _github_cache
    from PIL import Image, ImageDraw

    raw = _svg_path_points(GITHUB_PATH)
    xs = [p[0] for p in raw]
    ys = [p[1] for p in raw]
    x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    scale = 1.0 / max(w, h)

    def render(color):
        s = size * 8
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        pad = s * 0.02
        span = s - 2 * pad
        pts = [(pad + (x - x0) * scale * span, pad + (y - y0) * scale * span)
               for x, y in raw]
        ImageDraw.Draw(img).polygon(pts, fill=color)
        return img.resize((size, size), Image.LANCZOS)

    _github_cache = ctk.CTkImage(
        light_image=render((178, 94, 9, 255)),   # ACCENT claro
        dark_image=render((245, 165, 36, 255)),  # ACCENT escuro
        size=(size, size)
    )
    return _github_cache


class LangPicker(ctk.CTkButton):
    """Seletor de idioma do rodapé: discreto, com chevron e menu no clique."""

    def __init__(self, master, values, variable, **kwargs):
        super().__init__(
            master, textvariable=variable, command=self._open,
            font=ui_font(11), height=24, width=10, corner_radius=12,
            fg_color="transparent", hover_color=SURFACE2, text_color=MUTED,
            image=_chevron_image(11), compound="right", anchor="e", **kwargs
        )
        self._values = values
        self._var = variable

    def _open(self):
        menu = tk.Menu(
            self, tearoff=0, bd=0, relief="flat",
            bg=_pick(SURFACE), fg=_pick(TEXT),
            activebackground=_pick(SURFACE2), activeforeground=_pick(TEXT),
            font=(UI_FAMILY, 11)
        )
        for v in self._values:
            menu.add_command(label=f"  {v}  ",
                             command=lambda val=v: self._var.set(val))
        menu.tk_popup(self.winfo_rootx(),
                      self.winfo_rooty() - 8 - 24 * len(self._values))


class Dropdown(ctk.CTkFrame):
    """Campo de seleção: valor à esquerda, chevron nítido à direita, tk.Menu."""

    def __init__(self, master, values, variable, height=32, **kwargs):
        super().__init__(master, fg_color=SURFACE2, corner_radius=8,
                         border_width=1, border_color=BORDER,
                         height=height, **kwargs)
        self._values = values
        self._var = variable
        self.pack_propagate(False)

        self._label = ctk.CTkLabel(self, textvariable=variable,
                                   font=ui_font(13), text_color=TEXT, anchor="w")
        self._label.pack(side="left", fill="x", expand=True, padx=(12, 4))

        self._chev = ctk.CTkLabel(self, text="", image=_chevron_image(), width=18)
        self._chev.pack(side="right", padx=(0, 10))

        for w in (self, self._label, self._chev):
            w.bind("<Button-1>", self._open)

    def _open(self, event=None):
        menu = tk.Menu(
            self, tearoff=0, bd=0, relief="flat",
            bg=_pick(SURFACE), fg=_pick(TEXT),
            activebackground=_pick(SURFACE2), activeforeground=_pick(TEXT),
            font=(UI_FAMILY, 11)
        )
        for v in self._values:
            menu.add_command(label=f"  {v}  ",
                             command=lambda val=v: self._var.set(val))
        menu.tk_popup(self.winfo_rootx(),
                      self.winfo_rooty() + self.winfo_height() + 2)


# ─── Forma de onda (assinatura visual do app) ────────────────────────────────
#
# Cada arquivo ganha uma forma de onda própria — determinística, derivada dos
# bytes do áudio (não é amplitude real; é a assinatura visual dele). O mesmo
# motivo aparece três vezes, sempre com função: convite no dropzone (pulsa ao
# arrastar por cima), progresso pulsante enquanto transcreve e seek do player.

def _waveform_heights(path, n=64):
    """Alturas 0.10–1.0 com cara de fala (rajadas e pausas), estáveis por arquivo."""
    if path:
        try:
            with open(path, "rb") as f:
                head = f.read(65536)
            seed = zlib.crc32(head) ^ os.path.getsize(path)
        except Exception:
            seed = zlib.crc32(str(path).encode("utf-8", "ignore"))
    else:
        seed = 42  # onda genérica do dropzone
    rng = random.Random(seed)
    heights, level = [], rng.uniform(0.35, 0.75)
    for _ in range(n):
        level += rng.uniform(-0.28, 0.28)
        if rng.random() < 0.08:      # pausa na fala
            level = rng.uniform(0.10, 0.22)
        level = max(0.10, min(1.0, level))
        heights.append(level)
    return heights


class WaveStrip(tk.Canvas):
    """Faixa de barras de onda. ratio pinta o trecho tocado; pulse anima."""

    def __init__(self, master, heights, height=26, bg_tuple=SURFACE,
                 seek_cb=None, **kwargs):
        super().__init__(master, height=height, highlightthickness=0,
                         bg=_pick(bg_tuple),
                         cursor="hand2" if seek_cb else "arrow", **kwargs)
        self._heights = heights
        self._bg_t = bg_tuple
        self._ratio = 0.0
        self._phase = None       # None = parado; float = fase do pulso
        self._pulse_id = None
        self._seek_cb = seek_cb
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Destroy>", self._on_destroy)
        if seek_cb:
            self.bind("<Button-1>", self._on_seek)
            self.bind("<B1-Motion>", self._on_seek)
        try:
            ctk.AppearanceModeTracker.add(self._on_theme)
        except Exception:
            pass

    def _on_theme(self, *_):
        try:
            self.redraw()
        except Exception:
            pass

    def _on_destroy(self, event=None):
        try:
            self.stop_pulse()
        except Exception:
            pass
        try:
            ctk.AppearanceModeTracker.remove(self._on_theme)
        except Exception:
            pass

    def set_ratio(self, ratio: float):
        self._ratio = max(0.0, min(ratio, 1.0))
        self.redraw()

    def start_pulse(self):
        if self._pulse_id is None:
            self._phase = 0.0
            self._tick()

    def stop_pulse(self):
        if self._pulse_id:
            self.after_cancel(self._pulse_id)
            self._pulse_id = None
        if self._phase is not None:
            self._phase = None
            try:
                self.redraw()
            except Exception:
                pass

    def _tick(self):
        self._phase += 0.5
        self.redraw()
        self._pulse_id = self.after(90, self._tick)

    def redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 4:
            return
        self.configure(bg=_pick(self._bg_t))
        self.delete("all")
        idle, amber = _pick(WAVE_IDLE), _pick(ACCENT)
        bar_w, gap = 3, 2
        n = max(8, w // (bar_w + gap))
        cut = int(n * self._ratio)
        mid = h / 2
        for i in range(n):
            v = self._heights[int(i * len(self._heights) / n)]
            if self._phase is not None:
                # pulso: aceno de âmbar percorrendo as barras
                s = math.sin(self._phase - i * 0.35)
                v *= 0.72 + 0.28 * s * s
                color = amber if s > 0.45 else idle
            else:
                color = amber if i < cut else idle
            bh = max(2, v * (h - 4))
            x = i * (bar_w + gap)
            self.create_rectangle(x, mid - bh / 2, x + bar_w, mid + bh / 2,
                                  fill=color, outline="")

    def _on_seek(self, event):
        w = self.winfo_width()
        if w > 0 and self._seek_cb:
            self._seek_cb(max(0.0, min(event.x / w, 1.0)))


# ─── DropZone ─────────────────────────────────────────────────────────────────

class DropZone(ctk.CTkFrame):
    """Zona de arrastar/clicar. Grande quando vazia; barra fina quando há cards."""

    def __init__(self, master, on_files_cb, **kwargs):
        super().__init__(master, **kwargs)
        self.on_files_cb = on_files_cb
        self.configure(corner_radius=14, height=180)
        self._compact = False
        self._highlight = False
        self._apply_style()
        self._build()
        self._bind_drag()
        self.pack_propagate(False)

    def _apply_style(self):
        """Herói: sem caixa (borda âmbar só ao arrastar). Compacto: barra com borda."""
        if self._compact:
            self.configure(fg_color=SURFACE,
                           border_width=2 if self._highlight else 1,
                           border_color=ACCENT if self._highlight else BORDER)
        else:
            self.configure(fg_color="transparent",
                           border_width=2 if self._highlight else 0,
                           border_color=ACCENT)

    def _build(self):
        # Modo expandido
        self._full_box = ctk.CTkFrame(self, fg_color="transparent")
        self._full_box.pack(expand=True, fill="both")

        inner = ctk.CTkFrame(self._full_box, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        self._badge = ctk.CTkLabel(inner, text="", image=_plus_badge())
        self._badge.pack(pady=(0, 12))

        self._title_lbl = ctk.CTkLabel(
            inner, text=tr("drop_title"),
            font=display_font(18), text_color=TEXT
        )
        self._title_lbl.pack()

        # Onda-convite: pulsa quando um arquivo é arrastado por cima
        self._decor = WaveStrip(inner, _waveform_heights(None),
                                height=26, bg_tuple=BG, width=320)
        self._decor.pack(pady=(8, 6))

        self._sub_lbl = ctk.CTkLabel(
            inner, text=tr("drop_sub"),
            font=ui_font(11), text_color=MUTED
        )
        self._sub_lbl.pack()
        ctk.CTkLabel(
            inner, text="mp3 · m4a · ogg · opus · wav · webm · flac",
            font=mono_font(10), text_color=MUTED
        ).pack(pady=(5, 0))

        # Modo compacto (barra fina)
        self._bar_label = ctk.CTkLabel(
            self, text=tr("drop_more"),
            font=ui_font(12), text_color=MUTED
        )

        self._clickables = [self, self._full_box, inner, self._bar_label]
        self._clickables += list(inner.winfo_children())
        for w in self._clickables:
            w.bind("<Button-1>", self._on_click)

    def retranslate(self):
        self._title_lbl.configure(text=tr("drop_title"))
        self._sub_lbl.configure(text=tr("drop_sub"))
        self._bar_label.configure(text=tr("drop_more"))

    def set_compact(self, compact: bool):
        """Colapsa para barra de ~46px quando já existem cards na tela."""
        if compact == self._compact:
            return
        self._compact = compact
        if compact:
            self._full_box.pack_forget()
            self._bar_label.pack(expand=True, fill="both")
            self.configure(height=46)
        else:
            self._bar_label.pack_forget()
            self._full_box.pack(expand=True, fill="both")
            self.configure(height=180)
        self._apply_style()
        self.pack_propagate(False)

    def _bind_drag(self):
        try:
            # DND_Files garante que só arquivos são aceitos e entrega lista completa
            self.drop_target_register("DND_Files")
            self.dnd_bind("<<Drop>>", self._on_drop_tkdnd)
            self.dnd_bind("<<DropEnter>>", lambda e: self.set_highlight(True))
            self.dnd_bind("<<DropLeave>>", lambda e: self.set_highlight(False))
        except Exception:
            try:
                self.drop_target_register("*")
                self.dnd_bind("<<Drop>>", self._on_drop_tkdnd)
            except Exception:
                pass

    def _on_click(self, event=None):
        paths = filedialog.askopenfilenames(filetypes=[
            (tr("audio_files"), "*.mp3 *.mp4 *.m4a *.ogg *.oga *.opus *.wav *.webm *.flac"),
            (tr("all_files"), "*.*")
        ])
        if paths:
            self.on_files_cb(list(paths))

    def _on_drop_tkdnd(self, event):
        import re
        self.set_highlight(False)
        raw = event.data.strip()
        paths = []
        for m in re.finditer(r'\{([^}]+)\}|([^\s{}]+)', raw):
            p = m.group(1) or m.group(2)
            if p:
                paths.append(p)
        if paths:
            self.on_files_cb(paths)

    def set_highlight(self, active: bool):
        self._highlight = active
        self._apply_style()
        try:
            if active and not self._compact:
                self._decor.start_pulse()
            else:
                self._decor.stop_pulse()
        except Exception:
            pass


# ─── Áudio: utilitários ───────────────────────────────────────────────────────

def _get_audio_duration(path: str) -> float:
    """Retorna duração em segundos, ou 0.0 se não conseguir."""
    if not _MUTAGEN_OK:
        return 0.0
    try:
        audio = mutagen.File(path)
        if audio is not None and hasattr(audio, "info") and hasattr(audio.info, "length"):
            return float(audio.info.length)
    except Exception:
        pass
    return 0.0


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


_temp_wav_files: list[str] = []  # rastreia temporários para limpar ao fechar


def _to_playable_path(path: str) -> str:
    """
    Se o arquivo for OGG/Opus, converte para WAV temporário via pyogg.
    SDL2 suporta OGG/Vorbis mas não OGG/Opus (codec diferente).
    Retorna o path original para outros formatos.
    """
    ext = Path(path).suffix.lower()
    if ext not in NEEDS_CONVERSION or not _PYOGG_OK:
        return path

    try:
        import wave, tempfile
        opus = pyogg.OpusFile(path)
        # mkstemp (e não mktemp): cria o arquivo já com permissão do usuário,
        # sem a janela de corrida em que outro processo poderia tomar o nome.
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(opus.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(opus.frequency)
            wf.writeframes(bytes(opus.buffer))
        _temp_wav_files.append(tmp)
        return tmp
    except Exception:
        # fallback: tenta carregar direto mesmo que possa falhar
        return path


# ─── AudioPlayer ──────────────────────────────────────────────────────────────

class AudioPlayer(ctk.CTkFrame):
    """Player em uma linha: botão redondo, forma de onda clicável e tempo."""

    _active_player = None  # referência global ao player tocando (singleton)

    def __init__(self, master, path: str, duration: float = 0.0,
                 heights=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="transparent")
        self._path = _to_playable_path(path)          # converte Opus→WAV se necessário
        self._duration = duration or _get_audio_duration(path)
        self._heights = heights or _waveform_heights(path)
        self._playing = False
        self._seek_offset = 0.0
        self._play_start = 0.0
        self._poll_id = None
        self._loaded = False
        self._can_seek = Path(self._path).suffix.lower() in SEEK_SUPPORTED
        self._build()

    def _build(self):
        import time
        self._time_mod = time

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")

        self.play_btn = ctk.CTkButton(
            row, text="▶", width=30, height=30,
            font=ui_font(12), corner_radius=15,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color=ON_ACCENT,
            command=self._toggle
        )
        self.play_btn.pack(side="left", padx=(0, 10))

        self.wave = WaveStrip(
            row, self._heights, height=30, bg_tuple=SURFACE,
            seek_cb=self._seek_to_ratio if self._can_seek else None
        )
        self.wave.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.time_label = ctk.CTkLabel(
            row,
            text=f"0:00 / {_fmt_time(self._duration) if self._duration else '--:--'}",
            font=mono_font(10), text_color=MUTED, anchor="e"
        )
        self.time_label.pack(side="left")

    def _draw_bar(self, ratio: float):
        self.wave.set_ratio(ratio)

    def _current_ratio(self) -> float:
        if not self._duration:
            return 0.0
        return min(self._current_pos() / self._duration, 1.0)

    def _current_pos(self) -> float:
        """Posição atual em segundos, levando seek em conta."""
        if not _PYGAME_OK or not self._loaded:
            return self._seek_offset
        if self._playing:
            elapsed = self._time_mod.monotonic() - self._play_start
            return min(self._seek_offset + elapsed, self._duration or float("inf"))
        return self._seek_offset

    def _toggle(self):
        if not _PYGAME_OK:
            messagebox.showwarning(tr("audio_na_title"), tr("audio_na_body"))
            return
        if self._playing:
            self._pause()
        else:
            self._play()

    def _play(self):
        # Para qualquer outro player ativo
        if AudioPlayer._active_player and AudioPlayer._active_player is not self:
            AudioPlayer._active_player._pause()

        if not self._loaded:
            try:
                pygame.mixer.music.load(self._path)
                self._loaded = True
            except Exception as e:
                messagebox.showerror(tr("audio_load_error"), str(e))
                return

        if self._seek_offset > 0 and self._can_seek:
            pygame.mixer.music.play(start=self._seek_offset)
        else:
            pygame.mixer.music.play()

        self._play_start = self._time_mod.monotonic()
        self._playing = True
        AudioPlayer._active_player = self
        self.play_btn.configure(text="⏸")
        self._poll()

    def _pause(self):
        if not _PYGAME_OK:
            return
        self._seek_offset = self._current_pos()
        pygame.mixer.music.stop()
        self._playing = False
        self.play_btn.configure(text="▶")
        self._stop_poll()

    def _stop_poll(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None

    def _poll(self):
        """Atualiza barra/tempo a cada 180ms apenas enquanto toca."""
        if not self._playing:
            return
        pos = self._current_pos()
        if self._duration and pos >= self._duration:
            self._seek_offset = 0.0
            self._playing = False
            self.play_btn.configure(text="▶")
            self._draw_bar(0.0)
            self.time_label.configure(text=f"0:00 / {_fmt_time(self._duration)}")
            return
        ratio = (pos / self._duration) if self._duration else 0.0
        self._draw_bar(ratio)
        dur_str = _fmt_time(self._duration) if self._duration else "--:--"
        self.time_label.configure(text=f"{_fmt_time(pos)} / {dur_str}")
        self._poll_id = self.after(180, self._poll)

    def _seek_to_ratio(self, ratio: float):
        if not self._can_seek or not self._duration:
            return
        target = max(0.0, min(ratio * self._duration, self._duration))
        was_playing = self._playing
        if was_playing:
            self._stop_poll()
            pygame.mixer.music.stop()
            self._playing = False
        self._seek_offset = target
        self._draw_bar(ratio)
        self.time_label.configure(text=f"{_fmt_time(target)} / {_fmt_time(self._duration)}")
        if was_playing:
            self._play()

    def destroy(self):
        self._stop_poll()
        if AudioPlayer._active_player is self:
            if _PYGAME_OK:
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
            AudioPlayer._active_player = None
        super().destroy()


# ─── TranscriptionCard ────────────────────────────────────────────────────────

class TranscriptionCard(ctk.CTkFrame):
    """Card compacto por arquivo: header em uma linha, player, texto e ações."""

    def __init__(self, master, filename: str, audio_path: str,
                 on_remove, get_cfg, get_api_key, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=SURFACE, corner_radius=10,
                       border_color=BORDER, border_width=1)
        self._filename = filename
        self._audio_path = audio_path
        self._on_remove = on_remove
        self._get_cfg = get_cfg
        self._get_api_key = get_api_key
        self._player = None
        self._duration = _get_audio_duration(audio_path)
        self._build()

    def _build(self):
        # ── Header: nome + fechar; meta em mono logo abaixo ───────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 0))

        self.name_label = ctk.CTkLabel(
            hdr, text=self._filename,
            font=ui_font(13, "bold"), text_color=TEXT, anchor="w"
        )
        self.name_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            hdr, text="✕", width=24, height=24,
            fg_color="transparent", hover_color=SURFACE2,
            text_color=MUTED, corner_radius=6, font=ui_font(12),
            command=self._remove
        ).pack(side="right")

        self.meta_label = ctk.CTkLabel(
            self, text=_fmt_time(self._duration) if self._duration else "",
            font=mono_font(10), text_color=MUTED, anchor="w"
        )
        self.meta_label.pack(fill="x", padx=14)

        # ── Enquanto transcreve: a onda do arquivo pulsa (vira o player) ──
        self._heights = _waveform_heights(self._audio_path)
        self.pending_box = ctk.CTkFrame(self, fg_color="transparent")
        self.pending_box.pack(fill="x", padx=14, pady=(6, 0))

        self._pending_wave = WaveStrip(self.pending_box, self._heights,
                                       height=30, bg_tuple=SURFACE)
        self._pending_wave.pack(fill="x")
        self._pending_wave.start_pulse()

        self.stage_label = ctk.CTkLabel(
            self.pending_box, text=tr("queued"),
            font=mono_font(10), text_color=MUTED, anchor="w"
        )
        self.stage_label.pack(fill="x")

        # ── Textbox (altura dinâmica definida em set_result) ──────────────
        self.textbox = ctk.CTkTextbox(
            self, font=ui_font(13),
            fg_color=BG, text_color=TEXT,
            border_color=BORDER, border_width=1,
            corner_radius=8, wrap="word", height=96
        )
        self.textbox.pack(fill="both", expand=True, padx=14, pady=(8, 0))
        self.textbox.bind("<KeyRelease>", self._update_count)
        self.textbox.configure(state="disabled")

        # ── Ações ──────────────────────────────────────────────────────────
        act = ctk.CTkFrame(self, fg_color="transparent")
        act.pack(fill="x", padx=14, pady=(8, 12))

        self.copy_btn = primary_button(act, tr("copy"), self._copy, width=90)
        self.copy_btn.pack(side="left", padx=(0, 6))

        self.save_btn = ghost_button(act, tr("save_txt"), self._save, width=100)
        self.save_btn.pack(side="left", padx=(0, 6))

        self.rewrite_btn = ghost_button(act, tr("rewrite"), self._toggle_rewrite_panel,
                                        width=110)
        self.rewrite_btn.pack(side="left")

        self.error_label = ctk.CTkLabel(
            act, text="", font=ui_font(11),
            text_color=DANGER, anchor="w", wraplength=340
        )
        self.error_label.pack(side="left", padx=(10, 0))

        # ── Painel Reescrever (oculto por padrão) ─────────────────────────
        self._rewrite_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=8,
            border_color=BORDER, border_width=1
        )

        rw_inner = ctk.CTkFrame(self._rewrite_panel, fg_color="transparent")
        rw_inner.pack(fill="x", padx=8, pady=6)

        self._rewrite_entry = ctk.CTkEntry(
            rw_inner,
            placeholder_text=tr("rewrite_ph"),
            font=ui_font(12), height=32,
            fg_color=SURFACE, border_color=BORDER, text_color=TEXT
        )
        self._rewrite_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._rewrite_entry.bind("<Return>", lambda e: self._run_rewrite())

        self._rewrite_run_btn = primary_button(rw_inner, tr("send"), self._run_rewrite,
                                               width=80)
        self._rewrite_run_btn.pack(side="left")

        self._rewrite_status = ctk.CTkLabel(
            self._rewrite_panel, text="", font=ui_font(11), text_color=MUTED
        )
        self._rewrite_status.pack(anchor="w", padx=10, pady=(0, 4))

        self._rewrite_visible = False

    # ── Reescrever ─────────────────────────────────────────────────────────

    def _toggle_rewrite_panel(self):
        if self._rewrite_visible:
            self._rewrite_panel.pack_forget()
            self._rewrite_visible = False
            self.rewrite_btn.configure(text=tr("rewrite"))
        else:
            self._rewrite_panel.pack(fill="x", padx=14, pady=(0, 4), before=self.textbox)
            self._rewrite_visible = True
            self.rewrite_btn.configure(text=tr("close"))
            self._rewrite_entry.focus_set()

    def _run_rewrite(self):
        prompt_cmd = self._rewrite_entry.get().strip()
        if not prompt_cmd:
            return
        text = self.get_text().strip()
        if not text:
            self._rewrite_status.configure(text=tr("rewrite_no_text"))
            return
        api_key = (self._get_api_key() or "").strip()
        if not api_key:
            self._rewrite_status.configure(text=tr("rewrite_no_key"))
            return

        cfg = self._get_cfg()
        self._rewrite_run_btn.configure(state="disabled", text="...")
        self._rewrite_status.configure(text=tr("rewrite_sending"))

        full_prompt = f"{prompt_cmd}\n\nTexto:\n\n{text}"

        def _call():
            try:
                payload = {
                    "model": cfg.get("gpt_model", "gpt-4.1-mini"),
                    "messages": [{"role": "user", "content": full_prompt}],
                    "temperature": 0.4
                }
                resp = requests.post(
                    f"{api_base(cfg)}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload, timeout=120
                )
                if resp.ok:
                    result = resp.json()["choices"][0]["message"]["content"].strip()
                    self.after(0, self._apply_rewrite, result)
                else:
                    err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    self.after(0, self._rewrite_status.configure, {"text": f"Erro: {err}"})
            except Exception as e:
                self.after(0, self._rewrite_status.configure, {"text": f"Erro: {e}"})
            finally:
                self.after(0, self._rewrite_run_btn.configure,
                           {"state": "normal", "text": "Enviar"})

        threading.Thread(target=_call, daemon=True).start()

    def _apply_rewrite(self, new_text: str):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", new_text)
        self._fit_textbox(new_text)
        self._update_count()
        self._rewrite_status.configure(text=tr("rewrite_done"))
        self.after(3000, lambda: self._rewrite_status.configure(text=""))

    # ── Resultado / erro ───────────────────────────────────────────────────

    def _fit_textbox(self, text: str):
        """Altura dinâmica: min 96, máx 320 px, estimando linhas do texto."""
        lines = 0
        for ln in text.splitlines() or [""]:
            lines += max(1, math.ceil(len(ln) / 90))
        px = lines * 21 + 24
        self.textbox.configure(height=min(320, max(96, px)))

    def retranslate(self):
        """Reaplica os textos após troca de idioma (preserva o conteúdo)."""
        self.copy_btn.configure(text=tr("copy"))
        self.save_btn.configure(text=tr("save_txt"))
        self.rewrite_btn.configure(
            text=tr("close") if self._rewrite_visible else tr("rewrite"))
        self._rewrite_entry.configure(placeholder_text=tr("rewrite_ph"))
        self._rewrite_run_btn.configure(text=tr("send"))
        self._update_count()

    def set_stage(self, msg: str):
        """Etapa atual (enviando ao Whisper, limpando com GPT...)."""
        try:
            self.stage_label.configure(text=msg)
        except Exception:
            pass

    def set_result(self, text: str):
        """Chamado após transcrição bem-sucedida."""
        self._pending_wave.stop_pulse()
        self.pending_box.destroy()
        if _PYGAME_OK and Path(self._audio_path).exists():
            self._player = AudioPlayer(self, self._audio_path,
                                       duration=self._duration,
                                       heights=self._heights)
            self._player.pack(fill="x", padx=14, pady=(6, 0), before=self.textbox)

        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)
        self._fit_textbox(text)
        self._update_count()

    def set_error(self, msg: str):
        """Chamado em caso de falha."""
        self._pending_wave.stop_pulse()
        self.stage_label.configure(text=tr("failed"), text_color=DANGER)
        self.error_label.configure(text=msg)
        self.textbox.configure(state="normal")

    def get_text(self) -> str:
        return self.textbox.get("1.0", "end-1c")

    def _update_count(self, event=None):
        n = len(self.textbox.get("1.0", "end-1c"))
        sep = "." if UI_LANG in ("pt", "es") else ","
        chars = f"{n:,} {tr('characters')}".replace(",", sep)
        dur = _fmt_time(self._duration) if self._duration else ""
        self.meta_label.configure(text=f"{dur} · {chars}" if dur else chars)

    # ── Ações ──────────────────────────────────────────────────────────────

    def _copy(self):
        text = self.get_text()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.copy_btn.configure(text=tr("copied"))
        self.after(2000, lambda: self.copy_btn.configure(text=tr("copy")))

    def _save(self):
        text = self.get_text()
        if not text.strip():
            return
        default = Path(self._audio_path).stem + "_transcricao.txt"
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", initialfile=default,
            filetypes=[(tr("txt_file"), "*.txt")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.save_btn.configure(text=tr("saved"))
            self.after(2000, lambda: self.save_btn.configure(text=tr("save_txt")))

    def _remove(self):
        if self._player:
            self._player.destroy()
        self._on_remove(self)
        self.destroy()


# ─── ConfigPanel ──────────────────────────────────────────────────────────────

class ConfigPanel(ctk.CTkScrollableFrame):
    """Aba Configurações: chave em memória, grid 2 colunas, prompt colapsável."""

    def __init__(self, master, cfg: dict, initial_key: str = "",
                 on_key_change=None, prompt_open=False, lang_var=None, **kwargs):
        super().__init__(master, **kwargs)
        self.cfg = cfg
        self._on_key_change = on_key_change
        # StringVar do idioma do áudio é do App — compartilhada com o seletor
        # da tela principal, então os dois ficam sempre sincronizados.
        self.lang_var = lang_var or ctk.StringVar(value=cfg.get("language", "auto"))
        self._key_visible = False
        self._prompt_open = False
        self.configure(fg_color="transparent")
        self._build(initial_key)
        if prompt_open:
            self._toggle_prompt()

    def _section(self, title):
        ctk.CTkLabel(
            self, text=title.upper(), font=mono_font(10), text_color=MUTED
        ).pack(anchor="w", pady=(16, 4), padx=4)

    def _build(self, initial_key: str):
        # ── API ────────────────────────────────────────────────────────────
        self._section(tr("sec_api"))

        key_card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=10,
                                border_color=BORDER, border_width=1)
        key_card.pack(fill="x", pady=3)

        key_row = ctk.CTkFrame(key_card, fg_color="transparent")
        key_row.pack(fill="x", padx=12, pady=(10, 2))

        ctk.CTkLabel(
            key_row, text=tr("lbl_key"), font=ui_font(13),
            text_color=TEXT, width=150, anchor="w"
        ).pack(side="left")

        self._eye_btn = ghost_button(key_row, tr("show"), self._toggle_key_visibility,
                                     width=76, height=32)
        self._eye_btn.pack(side="right", padx=(6, 0))

        self.key_entry = ctk.CTkEntry(
            key_row, placeholder_text="sk-...", show="•", height=32,
            font=ui_font(13), fg_color=SURFACE2,
            border_color=BORDER, text_color=TEXT
        )
        self.key_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        if initial_key:
            self.key_entry.insert(0, initial_key)
        self.key_entry.bind("<KeyRelease>", self._key_changed)

        hint_row = ctk.CTkFrame(key_card, fg_color="transparent")
        hint_row.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(
            hint_row, text=tr("key_hint"),
            font=ui_font(11), text_color=MUTED, anchor="w"
        ).pack(side="left", fill="x", expand=True)

        self._forget_btn = ghost_button(hint_row, tr("forget_key"),
                                        self._forget_key, width=118, height=26)
        self._forget_btn.pack(side="right")

        self._test_btn = ghost_button(hint_row, tr("test_key"),
                                      self._test_key, width=106, height=26)
        self._test_btn.pack(side="right", padx=(0, 6))

        self.key_status = ctk.CTkLabel(
            key_card, text="", font=mono_font(11), anchor="w", text_color=MUTED
        )
        # (packed sob demanda em _set_key_status)

        # Endpoint compatível com OpenAI v1 (opcional; padrão = OpenAI)
        url_row = ctk.CTkFrame(key_card, fg_color="transparent")
        url_row.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            url_row, text=tr("lbl_endpoint"), font=ui_font(13),
            text_color=TEXT, width=150, anchor="w"
        ).pack(side="left")

        self.url_entry = ctk.CTkEntry(
            url_row, placeholder_text=DEFAULT_BASE_URL, height=32,
            font=mono_font(11), fg_color=SURFACE2,
            border_color=BORDER, text_color=TEXT
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        saved_url = (self.cfg.get("base_url") or "").strip()
        if saved_url and saved_url != DEFAULT_BASE_URL:
            self.url_entry.insert(0, saved_url)
        self.url_entry.bind("<KeyRelease>", self._check_endpoint)

        ctk.CTkLabel(
            key_card, text=tr("endpoint_hint"),
            font=ui_font(11), text_color=MUTED, anchor="w"
        ).pack(fill="x", padx=12, pady=(0, 8))

        # ── Transcrição (2 colunas) ────────────────────────────────────────
        self._section(tr("sec_transcription"))

        grid1 = ctk.CTkFrame(self, fg_color="transparent")
        grid1.pack(fill="x", pady=3)
        grid1.grid_columnconfigure((0, 1), weight=1, uniform="cols")

        self.whisper_var = ctk.StringVar(value=self.cfg.get("whisper_model", "whisper-1"))
        self._grid_cell(grid1, 0, tr("lbl_whisper"), lambda p: Dropdown(
            p, values=WHISPER_MODELS, variable=self.whisper_var))

        # Mesma StringVar do seletor da tela principal — os dois andam juntos.
        self._grid_cell(grid1, 1, tr("lbl_audio_lang"), lambda p: Dropdown(
            p, values=LANGUAGES, variable=self.lang_var))
        # Trocar o idioma do áudio reflete no prompt padrão (se não houver
        # personalização) — ex.: áudio em japonês → prompt em japonês.
        self.lang_var.trace_add("write", lambda *_: self.refresh_prompt_language())

        # ── Limpeza GPT (2 colunas) ────────────────────────────────────────
        self._section(tr("sec_cleanup"))

        grid2 = ctk.CTkFrame(self, fg_color="transparent")
        grid2.pack(fill="x", pady=3)
        grid2.grid_columnconfigure((0, 1), weight=1, uniform="cols")

        self.cleanup_var = ctk.BooleanVar(value=self.cfg.get("apply_cleanup", True))
        self._grid_cell(grid2, 0, tr("lbl_cleanup"), lambda p: ctk.CTkSwitch(
            p, variable=self.cleanup_var, text="",
            progress_color=ACCENT
        ))

        self.gpt_var = ctk.StringVar(value=self.cfg.get("gpt_model", "gpt-4.1-mini"))
        self._grid_cell(grid2, 1, tr("lbl_gpt"), lambda p: Dropdown(
            p, values=GPT_MODELS, variable=self.gpt_var))

        # (O idioma da interface fica no seletor do rodapé — troca imediata.)

        # ── Prompt de limpeza (colapsável, fechado por padrão) ─────────────
        self._prompt_toggle = ctk.CTkButton(
            self, text=f"{tr('prompt_toggle')} ▸", command=self._toggle_prompt,
            fg_color="transparent", hover_color=SURFACE2,
            text_color=TEXT, anchor="w", height=32,
            corner_radius=8, font=ui_font(13, "bold")
        )
        self._prompt_toggle.pack(fill="x", pady=(16, 0))

        self._prompt_frame = ctk.CTkFrame(self, fg_color="transparent")

        ctk.CTkLabel(
            self._prompt_frame, text=tr("prompt_var"),
            font=ui_font(11), text_color=MUTED
        ).pack(anchor="w", padx=4, pady=(2, 4))

        self.prompt_box = ctk.CTkTextbox(
            self._prompt_frame, font=mono_font(11),
            fg_color=SURFACE, text_color=TEXT,
            border_color=BORDER, border_width=1, corner_radius=8, height=220
        )
        self.prompt_box.pack(fill="x")
        self.prompt_box.insert("1.0", effective_cleanup_prompt(self.cfg))

        prompt_foot = ctk.CTkFrame(self._prompt_frame, fg_color="transparent")
        prompt_foot.pack(fill="x", pady=(4, 0))

        self.prompt_hint = ctk.CTkLabel(
            prompt_foot, text="", font=mono_font(10), text_color=MUTED, anchor="w"
        )
        self.prompt_hint.pack(side="left", fill="x", expand=True)

        ghost_button(prompt_foot, tr("restore_prompt"), self._restore_prompt,
                     width=130, height=26).pack(side="right")
        self._sync_prompt_hint()

        # ── Salvar ─────────────────────────────────────────────────────────
        save_row = ctk.CTkFrame(self, fg_color="transparent")
        save_row.pack(fill="x", pady=(16, 4))

        self.save_status = ctk.CTkLabel(
            save_row, text="", font=ui_font(12), text_color=SUCCESS
        )
        self.save_status.pack(side="left")

        primary_button(save_row, tr("save_settings"), self.save,
                       width=190).pack(side="right")

    def _grid_cell(self, grid, col, label, widget_cb):
        cell = ctk.CTkFrame(grid, fg_color=SURFACE, corner_radius=10,
                            border_color=BORDER, border_width=1)
        cell.grid(row=0, column=col, sticky="nsew",
                  padx=(0, 6) if col == 0 else (6, 0))
        ctk.CTkLabel(
            cell, text=label, font=ui_font(13), text_color=TEXT, anchor="w"
        ).pack(fill="x", padx=12, pady=(8, 2))
        w = widget_cb(cell)
        w.pack(fill="x", padx=12, pady=(0, 10))
        return w

    def _toggle_key_visibility(self):
        self._key_visible = not self._key_visible
        self.key_entry.configure(show="" if self._key_visible else "•")
        self._eye_btn.configure(text=tr("hide") if self._key_visible else tr("show"))

    def _toggle_prompt(self):
        self._prompt_open = not self._prompt_open
        arrow = "▾" if self._prompt_open else "▸"
        self._prompt_toggle.configure(text=f"{tr('prompt_toggle')} {arrow}")
        if self._prompt_open:
            self._prompt_frame.pack(fill="x", after=self._prompt_toggle)
        else:
            self._prompt_frame.pack_forget()

    def _key_changed(self, event=None):
        if self._on_key_change:
            self._on_key_change()

    def _check_endpoint(self, event=None):
        """Avisa se o endpoint digitado mandaria a chave sem criptografia."""
        if is_insecure_endpoint(self.url_entry.get()):
            self._set_key_status(tr("endpoint_insecure"), DANGER)

    # ── Prompt de limpeza ──────────────────────────────────────────────────

    def _sync_prompt_hint(self):
        """Diz se o prompt em uso é o padrão de um idioma ou personalizado."""
        text = self.prompt_box.get("1.0", "end-1c")
        if is_custom_prompt(text):
            self.prompt_hint.configure(text=tr("prompt_custom"))
        else:
            self.prompt_hint.configure(
                text=tr("prompt_default", lang=prompt_lang(self.cfg)))

    def _restore_prompt(self):
        """Volta ao prompt padrão do idioma corrente."""
        self.cfg["cleanup_prompt"] = ""
        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", default_cleanup_prompt(self.cfg))
        self._sync_prompt_hint()

    def refresh_prompt_language(self):
        """Reaplica o prompt padrão quando o idioma muda (se não houver
        personalização). Chamado ao trocar o idioma do áudio."""
        text = self.prompt_box.get("1.0", "end-1c")
        if is_custom_prompt(text):
            return
        new = default_cleanup_prompt(self.collect_language_only())
        if new.strip() != text.strip():
            self.prompt_box.delete("1.0", "end")
            self.prompt_box.insert("1.0", new)
        self._sync_prompt_hint()

    def collect_language_only(self) -> dict:
        """cfg com o idioma de áudio atual do widget (para resolver o prompt)."""
        return {**self.cfg, "language": self.lang_var.get()}

    def get_api_key(self) -> str:
        """Chave de API atual (campo). Persistida só via cofre, nunca no JSON."""
        return self.key_entry.get().strip()

    def persist_key(self) -> bool:
        """Grava a chave do campo no Gerenciador de Credenciais, se mudou."""
        key = self.get_api_key()
        if key and vault_read() != key:
            return vault_write(key)
        return False

    def _forget_key(self):
        """Apaga a chave do cofre e do campo."""
        vault_delete()
        self.key_entry.delete(0, "end")
        self._set_key_status(tr("key_removed"), MUTED)
        if self._on_key_change:
            self._on_key_change()

    # ── Testar chave (GET {base}/models) ───────────────────────────────────

    def _set_key_status(self, text, color):
        self.key_status.configure(text=text, text_color=color)
        if text and not self.key_status.winfo_ismapped():
            self.key_status.pack(fill="x", padx=12, pady=(0, 8))
        if text:
            self.after(8000, lambda: self.key_status.configure(text=""))

    def _test_key(self):
        key = self.get_api_key()
        if not key:
            self._set_key_status(tr("test_enter_first"), DANGER)
            return
        base = api_base({"base_url": self.url_entry.get()})
        self._test_btn.configure(state="disabled", text=tr("testing"))
        self._set_key_status(tr("test_checking", base=base), MUTED)

        def _call():
            try:
                resp = requests.get(f"{base}/models",
                                    headers={"Authorization": f"Bearer {key}"},
                                    timeout=20)
                if resp.ok:
                    try:
                        n = len(resp.json().get("data", []))
                        msg = tr("test_valid", n=n)
                    except Exception:
                        msg = tr("test_valid_simple")
                    result = (msg, SUCCESS)
                elif resp.status_code == 401:
                    result = (tr("test_invalid"), DANGER)
                else:
                    result = (f"✗ HTTP {resp.status_code}: {resp.text[:120]}", DANGER)
            except requests.exceptions.Timeout:
                result = (tr("test_timeout"), DANGER)
            except requests.exceptions.ConnectionError:
                result = (tr("test_noconn"), DANGER)
            except Exception as e:
                result = (f"✗ {e}", DANGER)
            self.after(0, self._set_key_status, *result)
            self.after(0, lambda: self._test_btn.configure(
                state="normal", text=tr("test_key")))

        threading.Thread(target=_call, daemon=True).start()

    def collect(self) -> dict:
        """Atualiza self.cfg com o estado atual dos widgets (sem a chave).

        `ui_language` não entra aqui: quem manda é o seletor do rodapé.
        """
        self.cfg["base_url"] = self.url_entry.get().strip() or DEFAULT_BASE_URL
        self.cfg["whisper_model"] = self.whisper_var.get()
        self.cfg["language"] = self.lang_var.get() or "auto"
        self.cfg["apply_cleanup"] = self.cleanup_var.get()
        self.cfg["gpt_model"] = self.gpt_var.get()
        # Só grava o prompt se for personalizado; padrão fica vazio para
        # continuar acompanhando o idioma.
        text = self.prompt_box.get("1.0", "end-1c")
        self.cfg["cleanup_prompt"] = text if is_custom_prompt(text) else ""
        return self.cfg

    def save(self):
        save_config(self.collect())
        persisted = self.persist_key()
        self.save_status.configure(
            text=tr("settings_saved_key") if persisted else tr("settings_saved"))
        self.after(4000, lambda: self.save_status.configure(text=""))


# ─── App ──────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._post_init()

    def _post_init(self):
        global UI_LANG
        _detect_fonts(self)
        self.cfg, legacy_key, scrubbed = load_config()

        # Idioma da UI: escolha salva ou o do Windows (fallback inglês)
        UI_LANG = resolve_ui_lang(self.cfg)

        # Idioma do áudio: "auto" por padrão (o Whisper detecta); só um valor
        # escolhido pelo usuário fixa o idioma.
        if not self.cfg.get("language"):
            self.cfg["language"] = "auto"

        # Migração: prompt padrão antigo gravado em texto volta a ser "vazio"
        # (assim ele passa a acompanhar o idioma). Personalizações são mantidas.
        if self.cfg.get("cleanup_prompt") and not is_custom_prompt(self.cfg["cleanup_prompt"]):
            self.cfg["cleanup_prompt"] = ""
            try:
                save_config(self.cfg)
            except Exception:
                pass

        # Tema salvo (auto segue o Windows; claro/escuro são manuais)
        mode = self.cfg.get("appearance", "system")
        if mode in _THEME_ORDER:
            ctk.set_appearance_mode(mode)

        # Chave: cofre do Windows primeiro; config antigo migra para o cofre.
        vault_key = vault_read()
        self._initial_key = vault_key or legacy_key
        self._migrated_to_vault = False
        if legacy_key and not vault_key:
            self._migrated_to_vault = vault_write(legacy_key)

        self.title("Transcritor de Áudio de Zap")
        self.geometry("780x720")
        self.minsize(640, 560)
        self.configure(fg_color=BG)

        self._cards: list[TranscriptionCard] = []
        self._active_threads = 0
        self._pending_paths: list[str] = []

        # Idioma do áudio: uma só StringVar para os dois seletores (header e
        # ajustes) — mudar num lugar reflete no outro na hora.
        self.audio_lang_var = ctk.StringVar(value=self.cfg.get("language", "auto"))

        # Log com buffer + flush agrupado (evita travar em rajadas)
        self._log_buffer: list[str] = []
        self._log_flush_id = None

        # Ícone da janela (assets/icone.ico — no exe vem via sys._MEIPASS)
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            icon = os.path.join(base, "assets", "icone.ico")
            if os.path.exists(icon):
                self.iconbitmap(icon)
        except Exception:
            pass

        self._build()

        if scrubbed:
            self._log("Chave de API removida do config.json (texto plano).")
        if self._migrated_to_vault:
            self._log("Chave migrada para o Gerenciador de Credenciais do Windows.")
        self._refresh_status()

        # Barra de título acompanha o tema (agora e a cada mudança do Windows)
        self.after(80, lambda: _apply_titlebar_theme(self))
        try:
            ctk.AppearanceModeTracker.add(lambda *_: _apply_titlebar_theme(self))
        except Exception:
            pass

    # ── Construção da UI ───────────────────────────────────────────────────

    def _build(self):
        # ── Header fino: wordmark + navegação mono + status ────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(14, 10))

        # Wordmark: ponto âmbar (REC) + nome; fora do pt-BR, um "a.k.a." abaixo
        mark = ctk.CTkFrame(header, fg_color="transparent")
        mark.pack(side="left")

        name_row = ctk.CTkFrame(mark, fg_color="transparent")
        name_row.pack(anchor="w")

        ctk.CTkLabel(
            name_row, text="●", font=ui_font(13), text_color=ACCENT
        ).pack(side="left")
        ctk.CTkLabel(
            name_row, text="transcritor de áudio de zap",
            font=display_font(17), text_color=TEXT
        ).pack(side="left", padx=(6, 0))

        self.aka_lbl = ctk.CTkLabel(
            mark, text=tr("wordmark_aka"), font=ui_font(10),
            text_color=MUTED, anchor="w"
        )
        self._sync_aka()

        # Ação principal sempre à mão: transcreve o que estiver pendente ou
        # abre o seletor de arquivos quando não há nada na fila.
        self.header_submit_btn = ctk.CTkButton(
            header, text=tr("transcribe").upper(), command=self._header_submit,
            font=ui_font(12, "bold"), height=30, width=130, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT
        )
        self.header_submit_btn.pack(side="right", padx=(12, 0))

        self.status_pill = ctk.CTkButton(
            header, text=tr("status_ready"), font=mono_font(11),
            fg_color="transparent", hover_color=SURFACE2,
            text_color=SUCCESS, corner_radius=13, height=26, width=10,
            command=self._on_status_click
        )
        self.status_pill.pack(side="right", padx=(12, 0))

        self._nav_btns = {}
        for page, label in (("Log", tr("nav_log")),
                            ("Configurações", tr("nav_settings"))):
            btn = ctk.CTkButton(
                header, text=label, font=mono_font(11),
                fg_color="transparent", hover_color=SURFACE2,
                text_color=MUTED, corner_radius=13, height=26, width=10,
                command=lambda p=page: self._toggle_page(p)
            )
            btn.pack(side="right", padx=(0, 6))
            self._nav_btns[page] = btn

        # Tema manual: cicla auto → claro → escuro
        self.theme_btn = ctk.CTkButton(
            header, text="◐ auto", font=mono_font(11),
            fg_color="transparent", hover_color=SURFACE2,
            text_color=MUTED, corner_radius=13, height=26, width=10,
            command=self._cycle_theme
        )
        self.theme_btn.pack(side="right", padx=(0, 6))
        self._sync_theme_btn()

        # ── Páginas ────────────────────────────────────────────────────────
        self._page_container = ctk.CTkFrame(self, fg_color="transparent")
        self._page_container.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        self._pages = {
            "Transcrição": ctk.CTkFrame(self._page_container, fg_color="transparent"),
            "Configurações": ctk.CTkFrame(self._page_container, fg_color="transparent"),
            "Log": ctk.CTkFrame(self._page_container, fg_color="transparent"),
        }
        self._current_page = None

        self._build_transcription_page(self._pages["Transcrição"])
        self._build_config_page(self._pages["Configurações"])
        self._build_log_page(self._pages["Log"])
        self._build_footer()

        self._show_page("Transcrição")

    def _build_footer(self):
        """Crédito à esquerda; seletor de idioma da interface à direita."""
        footer = ctk.CTkFrame(self, fg_color="transparent", height=28)
        footer.pack(fill="x", padx=20, pady=(0, 10))

        # Idioma da interface — troca imediata, cada opção no próprio idioma
        cur = self.cfg.get("ui_language", "auto")
        self.ui_lang_var = ctk.StringVar(
            value=UI_LANG_NAMES.get(cur, UI_LANG_NAMES["auto"]))
        LangPicker(footer, values=[UI_LANG_NAMES[k] for k in UI_LANGUAGES],
                   variable=self.ui_lang_var).pack(side="right")
        self.ui_lang_var.trace_add("write", lambda *_: self._ui_lang_picked())

        credit = ctk.CTkFrame(footer, fg_color="transparent")
        credit.pack(side="left")

        self.footer_lbl = ctk.CTkLabel(
            credit, text=tr("footer_offer"), font=ui_font(11), text_color=MUTED
        )
        self.footer_lbl.pack(side="left")

        link = ctk.CTkLabel(
            credit, text="Felipe Drummond", font=ui_font(11, "bold"),
            text_color=ACCENT, image=_github_image(), compound="left", padx=6,
            cursor="hand2"
        )
        link.pack(side="left", padx=(6, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_URL))

    def _ui_lang_picked(self):
        chosen = self.ui_lang_var.get()
        code = next((c for c, n in UI_LANG_NAMES.items() if n == chosen), "auto")
        if code != self.cfg.get("ui_language", "auto"):
            self.cfg["ui_language"] = code
            self.apply_ui_language()

    def _show_page(self, name: str):
        if self._current_page == name:
            return
        for frame in self._pages.values():
            frame.pack_forget()
        self._pages[name].pack(fill="both", expand=True)
        self._current_page = name
        for page, btn in self._nav_btns.items():
            btn.configure(text_color=ACCENT if page == name else MUTED)

    def _toggle_page(self, name: str):
        """Botões do header alternam: clicar de novo volta para a Transcrição."""
        self._show_page("Transcrição" if self._current_page == name else name)

    # ── Tema manual ─────────────────────────────────────────────────────────

    def _cycle_theme(self):
        cur = self.cfg.get("appearance", "system")
        idx = _THEME_ORDER.index(cur) if cur in _THEME_ORDER else 0
        nxt = _THEME_ORDER[(idx + 1) % len(_THEME_ORDER)]
        self.cfg["appearance"] = nxt
        ctk.set_appearance_mode(nxt)
        save_config(self.cfg)
        self._sync_theme_btn()

    def _sync_aka(self):
        """Mostra o 'a.k.a.' só quando o nome não se explica sozinho (en/es)."""
        text = tr("wordmark_aka")
        self.aka_lbl.configure(text=text)
        if text:
            self.aka_lbl.pack(anchor="w", padx=(19, 0))
        else:
            self.aka_lbl.pack_forget()

    def _sync_theme_btn(self):
        self.theme_btn.configure(
            text=_theme_label(self.cfg.get("appearance", "system")))

    def _build_transcription_page(self, page):
        # Idioma do áudio à mão, sem entrar nos ajustes (mesma StringVar)
        lang_row = ctk.CTkFrame(page, fg_color="transparent")
        lang_row.pack(fill="x", pady=(0, 6))

        # Packed nesta ordem: com side="right", o primeiro fica mais à direita.
        Dropdown(lang_row, values=LANGUAGES, variable=self.audio_lang_var,
                 height=28, width=110).pack(side="right")

        self.main_lang_lbl = ctk.CTkLabel(
            lang_row, text=tr("lbl_audio_lang"), font=mono_font(10),
            text_color=MUTED
        )
        self.main_lang_lbl.pack(side="right", padx=(0, 8))

        # Sem cards, o dropzone é o herói e ocupa a página inteira;
        # com cards, colapsa para uma barra fina no topo.
        self.drop_zone = DropZone(page, on_files_cb=self.on_files)
        self.drop_zone.pack(fill="both", expand=True, pady=(0, 0))

        # Barra de arquivos pendentes (aparece após selecionar)
        self.file_bar = ctk.CTkFrame(page, fg_color=SURFACE, corner_radius=10,
                                     border_color=BORDER, border_width=1)

        self.file_bar_label = ctk.CTkLabel(
            self.file_bar, text="", font=mono_font(11),
            text_color=TEXT, anchor="w"
        )
        self.file_bar_label.pack(side="left", padx=12, pady=8, fill="x", expand=True)

        ctk.CTkButton(
            self.file_bar, text="✕", width=26, height=26,
            fg_color="transparent", hover_color=SURFACE2,
            text_color=MUTED, corner_radius=6, font=ui_font(12),
            command=self._clear_pending
        ).pack(side="right", padx=(0, 6))

        self.submit_btn = primary_button(self.file_bar, tr("transcribe"),
                                         self._on_submit, width=130)
        self.submit_btn.pack(side="right", padx=(0, 8))

        # O progresso vive dentro de cada card (onda pulsante + etapa);
        # o status geral fica na pílula do header.

        # Área scrollável para os cards — só entra na tela quando há cards
        # (evita scrollbar solta numa área vazia)
        self.cards_area = ctk.CTkScrollableFrame(
            page, fg_color="transparent", corner_radius=0
        )

        # Ações globais — fixas na base, só aparecem quando há cards
        self.global_actions = ctk.CTkFrame(page, fg_color="transparent")

        self.copy_all_btn = primary_button(self.global_actions, tr("copy_all"),
                                           self._copy_all, width=120)
        self.copy_all_btn.pack(side="left", padx=(0, 8))
        self.clear_all_btn = ghost_button(self.global_actions, tr("clear_all"),
                                          self._clear_all, width=120)
        self.clear_all_btn.pack(side="left")

    def _build_config_page(self, page, initial_key=None, prompt_open=False):
        self.config_panel = ConfigPanel(
            page, cfg=self.cfg,
            initial_key=self._initial_key if initial_key is None else initial_key,
            on_key_change=self._refresh_status,
            prompt_open=prompt_open,
            lang_var=self.audio_lang_var,
            fg_color="transparent"
        )
        self.config_panel.pack(fill="both", expand=True)

    # ── Troca de idioma ao vivo ────────────────────────────────────────────

    def apply_ui_language(self):
        """Reaplica todos os textos da UI sem reiniciar o app.

        Os cards (e as transcrições em andamento) são preservados: só o
        painel de ajustes é reconstruído, com os valores atuais.
        """
        global UI_LANG
        key = self.config_panel.get_api_key()
        prompt_open = self.config_panel._prompt_open
        self.cfg = self.config_panel.collect()
        UI_LANG = resolve_ui_lang(self.cfg)
        save_config(self.cfg)

        # Ajustes: reconstrói (são dezenas de rótulos) preservando o estado
        self.config_panel.destroy()
        self._build_config_page(self._pages["Configurações"],
                                initial_key=key, prompt_open=prompt_open)

        # Header, dropzone, cards e log: reaplicam os textos no lugar
        for page, key_name in (("Log", "nav_log"), ("Configurações", "nav_settings")):
            self._nav_btns[page].configure(text=tr(key_name))
        self._sync_theme_btn()
        self._sync_aka()
        self._refresh_status()
        self.drop_zone.retranslate()
        self.submit_btn.configure(text=tr("transcribe"))
        self.header_submit_btn.configure(text=tr("transcribe").upper())
        self.main_lang_lbl.configure(text=tr("lbl_audio_lang"))
        self.copy_all_btn.configure(text=tr("copy_all"))
        self.clear_all_btn.configure(text=tr("clear_all"))
        self.log_title.configure(text=tr("log_title"))
        self.log_clear_btn.configure(text=tr("clear"))
        self.footer_lbl.configure(text=tr("footer_offer"))
        for card in self._cards:
            card.retranslate()
        if self._pending_paths:
            self._refresh_file_bar()

    def _build_log_page(self, page):
        log_hdr = ctk.CTkFrame(page, fg_color="transparent")
        log_hdr.pack(fill="x", pady=(4, 6))

        self.log_title = ctk.CTkLabel(
            log_hdr, text=tr("log_title"),
            font=ui_font(13, "bold"), text_color=TEXT
        )
        self.log_title.pack(side="left")

        self.log_clear_btn = ghost_button(log_hdr, tr("clear"), self._clear_log,
                                          width=80, height=28)
        self.log_clear_btn.pack(side="right")

        self.log_box = ctk.CTkTextbox(
            page, font=mono_font(11),
            fg_color=SURFACE, text_color=MUTED,
            border_color=BORDER, border_width=1,
            corner_radius=10, wrap="word", state="disabled"
        )
        self.log_box.pack(fill="both", expand=True)

        # Descarrega o que foi logado antes do widget existir
        self._flush_log()

    # ── Chave de API (somente memória) ─────────────────────────────────────

    def get_api_key(self) -> str:
        if hasattr(self, "config_panel"):
            return self.config_panel.get_api_key()
        return self._initial_key

    # ── Status pill ─────────────────────────────────────────────────────────

    def _refresh_status(self):
        if self._active_threads > 0:
            self.status_pill.configure(text=tr("status_processing"), text_color=ACCENT)
        elif not self.get_api_key():
            self.status_pill.configure(text=tr("status_no_key"), text_color=DANGER)
        else:
            self.status_pill.configure(text=tr("status_ready"), text_color=SUCCESS)

    def _on_status_click(self):
        if not self.get_api_key():
            self._show_page("Configurações")
            try:
                self.config_panel.key_entry.focus_set()
            except Exception:
                pass

    # ── Seleção e submit ───────────────────────────────────────────────────

    def on_files(self, paths: list[str]):
        valid = []
        for raw in paths:
            path = raw.strip()
            if not Path(path).exists():
                self._log(f"ERRO: arquivo não encontrado: {path}")
                continue
            ext = Path(path).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                self._log(f"AVISO: extensão ignorada '{ext}' — {Path(path).name}")
                continue
            valid.append(path)

        if not valid:
            messagebox.showwarning(tr("no_valid_title"), tr("no_valid_body"))
            return

        # ACRESCENTA aos pendentes (segundo drop não substitui), deduplicando
        seen = set(self._pending_paths)
        for p in valid:
            if p not in seen:
                self._pending_paths.append(p)
                seen.add(p)

        self._refresh_file_bar()
        self.file_bar.pack(fill="x", pady=(6, 0), after=self.drop_zone)

    def _refresh_file_bar(self):
        """Rótulo dos arquivos pendentes (também usado ao trocar de idioma)."""
        pend = self._pending_paths
        if not pend:
            return
        if len(pend) == 1:
            size_mb = Path(pend[0]).stat().st_size / (1024 * 1024)
            self.file_bar_label.configure(
                text=tr("one_file", name=Path(pend[0]).name, mb=f"{size_mb:.1f}"))
        else:
            total_mb = sum(Path(p).stat().st_size for p in pend) / (1024 * 1024)
            self.file_bar_label.configure(
                text=tr("n_files", n=len(pend), mb=f"{total_mb:.1f}"))

    def _header_submit(self):
        """Botão do header: transcreve a fila ou abre o seletor de arquivos."""
        self._show_page("Transcrição")
        if self._pending_paths:
            self._on_submit()
        else:
            self.drop_zone._on_click()

    def _on_submit(self):
        if not self._pending_paths:
            return
        self.cfg = self.config_panel.collect()
        if not self.get_api_key():
            self._log("ERRO: chave de API não informada")
            messagebox.showwarning(tr("key_missing_title"), tr("key_missing_body"))
            self._show_page("Configurações")
            return

        # Persiste no cofre automaticamente (sem exigir clique em Salvar)
        if self.config_panel.persist_key():
            self._log("Chave salva no Gerenciador de Credenciais do Windows.")

        paths = list(self._pending_paths)
        self._clear_pending()

        for path in paths:
            self._dispatch(path)

    def _clear_pending(self):
        self._pending_paths = []
        self.file_bar.pack_forget()

    def _dispatch(self, path: str):
        """Cria card imediato e inicia thread de transcrição."""
        self.cfg["language"] = self.audio_lang_var.get() or "auto"
        card = TranscriptionCard(
            self.cards_area,
            filename=Path(path).name,
            audio_path=path,
            on_remove=self._on_card_removed,
            get_cfg=lambda: self.cfg,
            get_api_key=self.get_api_key,
        )
        card.pack(fill="x", pady=(0, 8), padx=2)
        self._cards.append(card)
        self._update_layout_for_cards()

        self._active_threads += 1
        self._refresh_status()

        api_key = self.get_api_key()  # snapshot para a thread
        threading.Thread(
            target=self._run_transcription,
            args=(path, card, api_key),
            daemon=True
        ).start()

    def _run_transcription(self, path: str, card: TranscriptionCard, api_key: str):
        try:
            result = transcribe_audio(
                path, self.cfg, api_key,
                progress_cb=lambda msg: self.after(0, card.set_stage, msg),
                log_cb=lambda msg: self.after(0, self._log, msg)
            )
            self.after(0, card.set_result, result)
            self.after(0, self._log, f"Concluído: {Path(path).name}")
        except requests.exceptions.ConnectionError:
            msg = tr("err_no_conn")
            self.after(0, self._log, f"ERRO: {msg}")
            self.after(0, card.set_error, msg)
        except requests.exceptions.Timeout:
            msg = tr("err_timeout")
            self.after(0, self._log, f"ERRO: {msg}")
            self.after(0, card.set_error, msg)
        except Exception as e:
            msg = str(e)
            self.after(0, self._log, f"ERRO: {msg}")
            self.after(0, self._log, traceback.format_exc())
            self.after(0, card.set_error, msg)
        finally:
            self.after(0, self._on_thread_done)

    def _on_thread_done(self):
        self._active_threads = max(0, self._active_threads - 1)
        if self._active_threads == 0:
            self._refresh_status()

    # ── Cards ──────────────────────────────────────────────────────────────

    def _on_card_removed(self, card: TranscriptionCard):
        if card in self._cards:
            self._cards.remove(card)
        self._update_layout_for_cards()

    def _update_layout_for_cards(self):
        """Alterna entre dropzone-herói (vazio) e barra fina + cards."""
        has_cards = bool(self._cards)
        self.drop_zone.set_compact(has_cards)
        if has_cards:
            self.drop_zone.pack_configure(fill="x", expand=False)
            if not self.cards_area.winfo_ismapped():
                self.cards_area.pack(fill="both", expand=True, pady=(8, 0))
            self.global_actions.pack(fill="x", pady=(6, 0))
        else:
            self.cards_area.pack_forget()
            self.global_actions.pack_forget()
            self.drop_zone.pack_configure(fill="both", expand=True)

    def _copy_all(self):
        texts = [c.get_text() for c in self._cards if c.get_text().strip()]
        if texts:
            combined = "\n\n---\n\n".join(texts)
            self.clipboard_clear()
            self.clipboard_append(combined)

    def _clear_all(self):
        for card in list(self._cards):
            card._remove()

    # ── Log (buffer + flush agrupado a cada ~120ms) ────────────────────────

    def _log(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_buffer.append(f"[{ts}] {msg}\n")
        if not hasattr(self, "log_box"):
            return
        if self._log_flush_id is None:
            self._log_flush_id = self.after(120, self._flush_log)

    def _flush_log(self):
        self._log_flush_id = None
        if not self._log_buffer or not hasattr(self, "log_box"):
            return
        chunk = "".join(self._log_buffer)
        self._log_buffer.clear()
        try:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", chunk)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        except Exception:
            pass

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")


# ─── Entry point ──────────────────────────────────────────────────────────────

def _set_dpi_awareness():
    """Fontes nítidas em telas escaladas (per-monitor DPI v2 quando disponível)."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def main():
    _set_dpi_awareness()

    try:
        from tkinterdnd2 import TkinterDnD

        class AppWithDnD(App, TkinterDnD.DnDWrapper):
            def __init__(self):
                ctk.CTk.__init__(self)
                self.TkdndVersion = TkinterDnD._require(self)
                self._post_init()

        app = AppWithDnD()
    except Exception:
        app = App()

    app.mainloop()

    # Limpa WAVs temporários criados para Opus
    for tmp in _temp_wav_files:
        try:
            os.unlink(tmp)
        except Exception:
            pass


if __name__ == "__main__":
    main()
