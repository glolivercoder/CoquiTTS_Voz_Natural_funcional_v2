import streamlit as st
from TTS.api import TTS
import os
import tempfile
from pydub import AudioSegment
from datetime import datetime
import json
import time

# Automatiza aceitação da licença Coqui XTTS v2
os.environ["COQUI_TOS_AGREED"] = "1"

# Lista de modelos recomendados (pode ser expandida)
MODELOS = {
    'Português': 'tts_models/multilingual/multi-dataset/xtts_v2',
    'Inglês': 'tts_models/en/ljspeech/tacotron2-DDC',
    'Espanhol': 'tts_models/es/mai/tacotron2-DDC',
    'Alemão': 'tts_models/de/thorsten/tacotron2-DCA',
    'Francês': 'tts_models/fr/mai/tacotron2-DDC',
    'Chinês': 'tts_models/zh-CN/baker/tacotron2-DDC-GST',
    'Holandês': 'tts_models/nl/mai/tacotron2-DDC',
    'YourTTS (multi)': 'tts_models/multilingual/multi-dataset/your_tts',
}

# Função para salvar e carregar perfis/modelos de voz
PERFIS_PATH = 'perfis_modelos.json'
def carregar_perfis():
    if os.path.exists(PERFIS_PATH):
        with open(PERFIS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []
def salvar_perfis(perfis):
    with open(PERFIS_PATH, 'w', encoding='utf-8') as f:
        json.dump(perfis, f, ensure_ascii=False, indent=2)

# Tabs principais
aba = st.sidebar.radio("Navegação", ["Síntese", "Modelos"])

if aba == "Síntese":
    st.set_page_config(page_title="CoquiTTS Básico", layout="centered")
    st.title("CoquiTTS - Demo Básica")

    # Carregar perfis/modelos salvos
    perfis = carregar_perfis()
    opcoes_perfis = ["Nenhum"] + [f"{p['nome']} ({p['genero']})" for p in perfis]
    perfil_selecionado = st.selectbox("Selecionar perfil/modelo de voz salvo:", opcoes_perfis)
    perfil_ativo = None
    if perfil_selecionado != "Nenhum":
        idx = opcoes_perfis.index(perfil_selecionado) - 1
        if idx >= 0:
            perfil_ativo = perfis[idx]

    # Seletor de idioma/modelo
    idioma = st.selectbox("Selecione o idioma/modelo:", list(MODELOS.keys()),
        index=list(MODELOS.keys()).index(perfil_ativo["idioma"]) if perfil_ativo else 0)
    modelo = MODELOS[idioma]

    # Seletor de dispositivo (CPU/GPU)
    dispositivo = st.selectbox("Selecione o dispositivo de processamento:", ["CPU", "GPU (se disponível)"])
    usa_gpu = dispositivo == "GPU (se disponível)"

    # Seletor de diretório para salvar áudios
    pasta_padrao = st.text_input("Pasta para salvar áudios gerados:", value=os.path.join(os.getcwd(), 'audios'))
    os.makedirs(pasta_padrao, exist_ok=True)

    # Área de texto
    texto = st.text_area("Digite o texto para síntese de voz:", "Olá, mundo! Este é um teste do CoquiTTS.")

    # Dropdown para exemplos de voz
    exemplo_dir = os.path.join(os.getcwd(), 'exemplos')
    exemplo_opcoes = ["Nenhum"]
    exemplo_map = {}
    if os.path.exists(exemplo_dir):
        for fname in sorted(os.listdir(exemplo_dir)):
            if fname.endswith('.wav') or fname.endswith('.mp3'):
                if fname.startswith('male_'):
                    label = f"Masculino - {fname}"
                elif fname.startswith('female_'):
                    label = f"Feminino - {fname}"
                else:
                    label = fname
                exemplo_opcoes.append(label)
                exemplo_map[label] = os.path.join(exemplo_dir, fname)
    exemplo_escolhido = st.selectbox("Escolha um exemplo de voz (ou envie um arquivo):", exemplo_opcoes)

    # Upload de áudio do usuário (captura de voz)
    st.markdown("**Opcional:** Faça upload de um arquivo de áudio (.wav ou .mp3) para usar como referência de voz (clonagem/voice sample). Só funciona com modelos compatíveis (XTTS v2, YourTTS). Se não enviar, pode escolher um exemplo acima.")
    audio_file = st.file_uploader("Envie um arquivo de áudio (WAV ou MP3)", type=["wav", "mp3"])
    if audio_file is not None:
        st.audio(audio_file, format="audio/wav" if audio_file.name.endswith('.wav') else "audio/mp3")
        st.info("Áudio carregado! Se o modelo selecionado for compatível, será usada a clonagem de voz.")
    elif exemplo_escolhido != "Nenhum":
        st.audio(exemplo_map[exemplo_escolhido], format="audio/wav" if exemplo_map[exemplo_escolhido].endswith('.wav') else "audio/mp3")
        st.info(f"Exemplo selecionado: {exemplo_escolhido}")

    def converter_para_wav(origem_path, destino_path):
        if origem_path.endswith('.wav'):
            return origem_path
        audio = AudioSegment.from_file(origem_path)
        audio.export(destino_path, format="wav")
        return destino_path

    def converter_bytes_para_wav(audio_bytes, ext):
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp_audio:
            tmp_audio.write(audio_bytes)
            tmp_audio_path = tmp_audio.name
        wav_path = tmp_audio_path.replace(f'.{ext}', '.wav')
        converter_para_wav(tmp_audio_path, wav_path)
        os.remove(tmp_audio_path)
        return wav_path

    # Dados para salvar perfil
    nome_perfil = st.text_input("Nome do perfil/modelo de voz (opcional):", value=perfil_ativo["nome"] if perfil_ativo else "")
    genero_perfil = st.selectbox("Gênero do perfil/modelo de voz:", ["Não especificado", "Masculino", "Feminino"],
        index=["Não especificado", "Masculino", "Feminino"].index(perfil_ativo["genero"]) if perfil_ativo else 0)

    # Se perfil/modelo salvo selecionado, usar o áudio de referência dele
    referencia_path_perfil = perfil_ativo["caminho_audio"] if perfil_ativo else None

    # Dropdown para formato de saída
    formato_saida = st.selectbox("Formato do áudio de saída:", ["wav", "ogg", "mp3"])

    # Aviso sobre limite de texto
    st.info("Recomendação: limite de até 500 caracteres por síntese (aprox. 30s a 1min de áudio). Para textos longos, divida em blocos.")

    # Botão para gerar áudio
    if st.button("Gerar Áudio"):
        with st.spinner("Gerando áudio..."):
            tts = TTS(modelo, gpu=usa_gpu)
            # Novo padrão: nome do perfil/modelo selecionado + lingua + data_hora
            lang_map_ext = {
                'Português': 'pt_br',
                'Inglês': 'en_us',
                'Espanhol': 'es_es',
                'Alemão': 'de_de',
                'Francês': 'fr_fr',
                'Chinês': 'zh_cn',
                'Holandês': 'nl_nl',
                'YourTTS (multi)': 'multi',
            }
            idioma_ext = lang_map_ext.get(idioma, 'xx')
            if perfil_ativo and perfil_ativo.get('nome'):
                nome_perfil_voz = perfil_ativo['nome'].replace(' ', '_')
            else:
                nome_perfil_voz = idioma.replace(' ', '_').lower()
            agora_br = datetime.now().strftime("%d-%m-%Y_%H-%M")
            nome_base = f"{nome_perfil_voz}_{idioma_ext}_{agora_br}"
            saida_wav = os.path.join(pasta_padrao, nome_base + ".wav")
            saida_final = os.path.join(pasta_padrao, f"{nome_base}.{formato_saida}")
            srt_path = os.path.join(pasta_padrao, f"{nome_base}.srt")
            referencia_path = None
            temp_wav_to_remove = None
            if audio_file is not None:
                ext = audio_file.name.split('.')[-1].lower()
                if ext == 'wav':
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio:
                        tmp_audio.write(audio_file.read())
                        referencia_path = tmp_audio.name
                else:
                    wav_path = converter_bytes_para_wav(audio_file.read(), ext)
                    referencia_path = wav_path
                    temp_wav_to_remove = wav_path
            elif perfil_selecionado != "Nenhum":
                referencia_path = referencia_path_perfil
            elif exemplo_escolhido != "Nenhum":
                exemplo_path = exemplo_map[exemplo_escolhido]
                if exemplo_path.endswith('.wav'):
                    referencia_path = exemplo_path
                else:
                    wav_path = exemplo_path.replace('.mp3', '.tmp.wav')
                    converter_para_wav(exemplo_path, wav_path)
                    referencia_path = wav_path
                    temp_wav_to_remove = wav_path
            lang_map = {
                'Português': 'pt',
                'Inglês': 'en',
                'Espanhol': 'es',
                'Alemão': 'de',
                'Francês': 'fr',
                'Chinês': 'zh',
                'Holandês': 'nl',
                'YourTTS (multi)': 'pt', # default
            }
            idioma_tts = lang_map.get(idioma, 'en')
            if referencia_path and modelo in [
                'tts_models/multilingual/multi-dataset/xtts_v2',
                'tts_models/multilingual/multi-dataset/your_tts',
            ]:
                tts.tts_to_file(
                    text=texto,
                    file_path=saida_wav,
                    speaker_wav=[referencia_path],
                    language=idioma_tts
                )
            else:
                tts.tts_to_file(text=texto, file_path=saida_wav)
            # Conversão para formato escolhido
            if formato_saida != "wav":
                # Aguarda o arquivo existir e ter tamanho > 0
                for _ in range(10):
                    if os.path.exists(saida_wav) and os.path.getsize(saida_wav) > 0:
                        break
                    time.sleep(0.1)
                if os.path.exists(saida_wav) and os.path.getsize(saida_wav) > 0:
                    audio = AudioSegment.from_wav(saida_wav)
                    audio.export(saida_final, format=formato_saida)
            else:
                saida_final = saida_wav
            # Geração do SRT simples
            with open(srt_path, "w", encoding="utf-8") as srt:
                srt.write("1\n00:00:00,000 --> 00:00:10,000\n" + texto.strip() + "\n")
            # Download dos arquivos
            if os.path.exists(saida_final):
                st.audio(saida_final, format=f"audio/{formato_saida}")
                with open(saida_final, "rb") as f:
                    st.download_button(f"Baixar Áudio ({formato_saida.upper()})", f, file_name=os.path.basename(saida_final), mime=f"audio/{formato_saida}")
            if os.path.exists(srt_path):
                with open(srt_path, "rb") as f:
                    st.download_button("Baixar Legenda (SRT)", f, file_name=os.path.basename(srt_path), mime="text/srt")
            st.success(f"Áudio salvo em: {saida_final}")
            # Só remova arquivos temporários após todas as operações
            if temp_wav_to_remove and os.path.exists(temp_wav_to_remove):
                os.remove(temp_wav_to_remove)
            elif audio_file is not None and referencia_path and os.path.exists(referencia_path):
                os.remove(referencia_path)
            # Salvar perfil/modelo de voz se nome foi informado
            if nome_perfil.strip() and referencia_path:
                pasta_perfis = os.path.join('Modelos', 'perfis')
                os.makedirs(pasta_perfis, exist_ok=True)
                nome_audio_perfil = f"{nome_perfil.strip().replace(' ', '_')}_{agora_br}.wav"
                caminho_audio_permanente = os.path.join(pasta_perfis, nome_audio_perfil)
                try:
                    # Se referencia_path for temporário, copie antes de remover
                    if audio_file is not None:
                        # Lê os bytes do arquivo de upload uma única vez
                        audio_bytes = audio_file.getvalue() if hasattr(audio_file, 'getvalue') else audio_file.read()
                        with open(caminho_audio_permanente, 'wb') as f:
                            f.write(audio_bytes)
                    else:
                        AudioSegment.from_file(referencia_path).export(caminho_audio_permanente, format="wav")
                except Exception as e:
                    st.error(f"Erro ao salvar áudio de referência permanente: {e}")
                    caminho_audio_permanente = referencia_path  # fallback
                perfis = carregar_perfis()
                perfis.append({
                    "nome": nome_perfil.strip(),
                    "genero": genero_perfil,
                    "caminho_audio": caminho_audio_permanente,
                    "modelo": modelo,
                    "idioma": idioma,
                    "data": agora_br
                })
                salvar_perfis(perfis)
                st.success(f"Perfil/modelo '{nome_perfil.strip()}' salvo!")

    # --- REMOVIDO: Gravação de voz em tempo real (não há biblioteca estável disponível) ---
    # (mantém apenas upload de áudio)

    st.markdown("---")
    st.markdown("""
    **Manual Rápido:**
    - Escolha o idioma/modelo desejado.
    - Digite o texto na área acima.
    - (Opcional) Faça upload de um arquivo de áudio para referência de voz (clonagem) ou escolha um exemplo.
    - Selecione CPU ou GPU.
    - Escolha a pasta de saída.
    - Clique em "Gerar Áudio" para ouvir e baixar o resultado.
    - (Opcional) Salve o perfil/modelo de voz criado.
    """)

elif aba == "Modelos":
    st.title("Perfis/Modelos de Voz Salvos")
    perfis = carregar_perfis()
    if not perfis:
        st.info("Nenhum perfil/modelo salvo ainda.")
    else:
        indices_para_excluir = []
        for i, perfil in enumerate(perfis):
            st.markdown(f"**Nome:** {perfil['nome']}")
            st.markdown(f"**Gênero:** {perfil['genero']}")
            st.markdown(f"**Modelo:** {perfil['modelo']}")
            st.markdown(f"**Idioma:** {perfil['idioma']}")
            st.markdown(f"**Data:** {perfil['data']}")
            if os.path.exists(perfil['caminho_audio']):
                st.audio(perfil['caminho_audio'], format="audio/wav")
            # Botão de exclusão com alerta
            if st.button(f"Excluir perfil: {perfil['nome']} ({perfil['genero']})", key=f"excluir_{i}"):
                if st.warning(f"Tem certeza que deseja excluir o perfil '{perfil['nome']}'? Esta ação não pode ser desfeita.", icon="⚠️") or True:
                    indices_para_excluir.append(i)
            st.markdown("---")
        # Excluir perfis após confirmação
        if indices_para_excluir:
            for idx in sorted(indices_para_excluir, reverse=True):
                perfil = perfis[idx]
                # Remover arquivo de áudio permanente, se existir
                if os.path.exists(perfil['caminho_audio']):
                    try:
                        os.remove(perfil['caminho_audio'])
                    except Exception as e:
                        st.warning(f"Não foi possível remover o áudio: {e}")
                del perfis[idx]
            salvar_perfis(perfis)
            st.success("Perfil/modelo excluído com sucesso!") 