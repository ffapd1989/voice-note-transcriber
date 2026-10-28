import json
import time

import customtkinter as ctk
import pytest
import requests

import transcricao_app as app

ERRO_DE_MODELO_SO_COM_TEMPERATURA_PADRAO = {
    "error": {
        "message": "Unsupported value: 'temperature' does not support 0.2 with this model. "
                   "Only the default (1) value is supported.",
        "type": "invalid_request_error",
        "param": "temperature",
        "code": "unsupported_value",
    }
}


def resposta(status: int, corpo) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp._content = (corpo if isinstance(corpo, str) else json.dumps(corpo)).encode("utf-8")
    return resp


def api_falsa(status_do_chat: int = 200):
    def post(url, **kwargs):
        if url.endswith("/audio/transcriptions"):
            return resposta(200, "texto bruto")
        if "temperature" in kwargs["json"]:
            return resposta(400, ERRO_DE_MODELO_SO_COM_TEMPERATURA_PADRAO)
        if status_do_chat != 200:
            return resposta(status_do_chat, {"error": {"message": "servidor fora do ar"}})
        return resposta(200, {"choices": [{"message": {"content": " texto limpo "}}]})
    return post


@pytest.fixture
def audio(tmp_path):
    arquivo = tmp_path / "audio.ogg"
    arquivo.write_bytes(b"\0" * 2048)
    return arquivo


@pytest.fixture
def cfg():
    return {**app.DEFAULT_CONFIG, "language": "pt", "apply_cleanup": True}


def test_limpeza_funciona_com_modelo_que_so_aceita_temperatura_padrao(monkeypatch, audio, cfg):
    monkeypatch.setattr(app.requests, "post", api_falsa())

    assert app.transcribe_audio(str(audio), cfg, "sk-teste") == "texto limpo"


def test_reescrita_funciona_com_modelo_que_so_aceita_temperatura_padrao(monkeypatch, cfg):
    monkeypatch.setattr(app.requests, "post", api_falsa())

    assert app.chat_completion(cfg, "sk-teste", "resuma", timeout=120) == "texto limpo"


def test_falha_na_limpeza_devolve_a_transcricao_ja_paga(monkeypatch, audio, cfg):
    monkeypatch.setattr(app.requests, "post", api_falsa(status_do_chat=500))

    with pytest.raises(app.CleanupError) as falha:
        app.transcribe_audio(str(audio), cfg, "sk-teste")

    assert falha.value.transcript == "texto bruto"
    assert "servidor fora do ar" in str(falha.value)


def test_erro_da_api_mostra_a_mensagem_e_nao_o_json():
    texto = app.api_error_text(resposta(400, ERRO_DE_MODELO_SO_COM_TEMPERATURA_PADRAO))

    assert texto.startswith("Unsupported value")
    assert "invalid_request_error" not in texto


def test_erro_da_api_sem_json_mostra_o_corpo():
    assert app.api_error_text(resposta(502, "Bad Gateway")) == "Bad Gateway"


def test_reescrita_com_erro_libera_o_botao_e_mostra_o_motivo(monkeypatch, audio, cfg):
    raiz = ctk.CTk()
    try:
        cartao = app.TranscriptionCard(raiz, audio.name, str(audio), on_remove=lambda _: None,
                                       get_cfg=lambda: cfg, get_api_key=lambda: "sk-teste")
        cartao.textbox.configure(state="normal")
        cartao.textbox.insert("1.0", "texto transcrito")
        cartao._rewrite_entry.insert(0, "resuma")
        monkeypatch.setattr(app.requests, "post", api_falsa(status_do_chat=500))

        limite = time.monotonic() + 5

        def esperar_a_resposta():
            if cartao._rewrite_run_btn.cget("state") == "disabled" and time.monotonic() < limite:
                raiz.after(20, esperar_a_resposta)
            else:
                raiz.quit()

        cartao._run_rewrite()
        raiz.after(20, esperar_a_resposta)
        raiz.mainloop()

        assert cartao._rewrite_run_btn.cget("state") == "normal"
        assert cartao._rewrite_run_btn.cget("text") == app.tr("send")
        assert "servidor fora do ar" in cartao._rewrite_status.cget("text")
    finally:
        raiz.destroy()
