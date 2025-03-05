import streamlit as st
import os
import json
import logging
import time
import requests
from google.cloud import texttospeech
from moviepy.editor import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from io import BytesIO
import nltk
from nltk.corpus import stopwords

# Descargar recursos para procesamiento de texto
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
    nltk.download('punkt')

logging.basicConfig(level=logging.INFO)

# Cargar credenciales de GCP desde secrets
credentials = dict(st.secrets.gcp_service_account)
with open("google_credentials.json", "w") as f:
    json.dump(credentials, f)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_credentials.json"

# Configuración de voces
VOCES_DISPONIBLES = {
    'es-ES-Standard-A': texttospeech.SsmlVoiceGender.FEMALE,
    'es-ES-Standard-B': texttospeech.SsmlVoiceGender.MALE,
    'es-ES-Standard-C': texttospeech.SsmlVoiceGender.FEMALE,
    # ... (resto de las voces)
}

# Función para crear un video abstracto básico (en caso de que no se cargue video)
def create_basic_background(duration=5, output_path="basic_bg.mp4"):
    try:
        # Crear una secuencia de frames con colores cambiantes
        frames = []
        fps = 24
        total_frames = int(duration * fps)

        width, height = 1280, 720

        for i in range(total_frames):
            # Crear un degradado de colores que cambia con el tiempo
            r = int(128 + 127 * np.sin(i * 0.02))
            g = int(128 + 127 * np.sin(i * 0.01))
            b = int(128 + 127 * np.sin(i * 0.03))

            # Crear imagen con ese color
            img = np.ones((height, width, 3), dtype=np.uint8)
            img[:, :, 0] = r
            img[:, :, 1] = g
            img[:, :, 2] = b

            frames.append(img)

        # Crear clip con los frames
        clip = ImageClip(frames[0]).set_duration(1/fps)
        for frame in frames[1:]:
            clip = concatenate_videoclips([clip, ImageClip(frame).set_duration(1/fps)])

        clip.write_videofile(output_path, fps=fps, codec='libx264', logger=None)
        return output_path
    except Exception as e:
        logging.error(f"Error al crear fondo básico: {str(e)}")
        return None

# Función de creación de texto
def create_text_image(text, size=(1280, 360), font_size=30, line_height=40, bg_color=(0, 0, 0, 180)):
    # Crear una imagen con canal alfa (transparente)
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Crear un rectángulo semi-transparente para el texto
    overlay = Image.new('RGBA', size, bg_color)
    img.paste(overlay, (0, 0), overlay)

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)

    words = text.split()
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        test_line = ' '.join(current_line)
        left, top, right, bottom = draw.textbbox((0, 0), test_line, font=font)
        if right > size[0] - 60:
            current_line.pop()
            lines.append(' '.join(current_line))
            current_line = [word]
    lines.append(' '.join(current_line))

    total_height = len(lines) * line_height
    y = (size[1] - total_height) // 2

    for line in lines:
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
        x = (size[0] - (right - left)) // 2
        draw.text((x, y), line, font=font, fill="white")
        y += line_height

    return np.array(img)

# Nueva función para crear la imagen de suscripción
def create_subscription_image(logo_url, size=(1280, 720), font_size=60):
    img = Image.new('RGBA', size, (255, 0, 0, 220))  # Fondo rojo semi-transparente
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)

    # Cargar logo del canal
    try:
        response = requests.get(logo_url)
        response.raise_for_status()
        logo_img = Image.open(BytesIO(response.content)).convert("RGBA")
        logo_img = logo_img.resize((100,100))
        logo_position = (20,20)
        img.paste(logo_img,logo_position,logo_img)
    except Exception as e:
        logging.error(f"Error al cargar el logo: {str(e)}")

    text1 = "¡SUSCRÍBETE A LECTOR DE SOMBRAS!"
    left1, top1, right1, bottom1 = draw.textbbox((0, 0), text1, font=font)
    x1 = (size[0] - (right1 - left1)) // 2
    y1 = (size[1] - (bottom1 - top1)) // 2 - (bottom1 - top1) // 2 - 20
    draw.text((x1, y1), text1, font=font, fill="white")

    font2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size//2)
    text2 = "Dale like y activa la campana 🔔"
    left2, top2, right2, bottom2 = draw.textbbox((0, 0), text2, font=font2)
    x2 = (size[0] - (right2 - left2)) // 2
    y2 = (size[1] - (bottom2 - top2)) // 2 + (bottom1 - top1) // 2 + 20
    draw.text((x2,y2), text2, font=font2, fill="white")

    return np.array(img)

# Función de creación de video simplificada
def create_simple_video_with_one_background(texto, nombre_salida, voz, logo_url, video_fondo):
    archivos_temp = []
    clips_audio = []
    clips_finales = []

    try:
        logging.info("Iniciando proceso de creación de video...")
        frases = [f.strip() + "." for f in texto.split('.') if f.strip()]
        client = texttospeech.TextToSpeechClient()

        # Cargar el video de fondo
        if video_fondo is not None:
            try:
                background_clip = VideoFileClip(video_fondo.name).resize(height=720)
            except Exception as e:
                logging.error(f"Error al cargar video de fondo: {str(e)}")
                background_clip = None
        else:
            background_clip = None


        for i, frase in enumerate(frases):
            logging.info(f"Procesando frase {i+1} de {len(frases)}")

            # Generar audio con Google TTS
            synthesis_input = texttospeech.SynthesisInput(text=frase)
            voice = texttospeech.VoiceSelectionParams(
                language_code="es-ES",
                name=voz,
                ssml_gender=VOCES_DISPONIBLES[voz]
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )

            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            temp_filename = f"audio_{i}.mp3"  # Nombre simplificado
            archivos_temp.append(temp_filename)
            with open(temp_filename, "wb") as out:
                out.write(response.audio_content)

            audio_clip = AudioFileClip(temp_filename)
            clips_audio.append(audio_clip)
            duracion = audio_clip.duration

            # Si no hay video de fondo cargado, crear un fondo básico
            if background_clip is None:
                basic_bg_path = "basic_bg.mp4"  # Nombre simplificado
                create_basic_background(duracion, basic_bg_path)
                background_clip = VideoFileClip(basic_bg_path)

            # Recortar o extender el video de fondo si es necesario
            if background_clip.duration < duracion:
                n_loops = int(duracion / background_clip.duration) + 1
                background_clip = background_clip.loop(n=n_loops).subclip(0, duracion)
            else:
                background_clip = background_clip.subclip(0, duracion)


            # Crear capa de texto semi-transparente
            text_img = create_text_image(frase)
            txt_clip = (ImageClip(text_img)
                      .set_duration(duracion)
                      .set_position(('center', 'bottom')))

            # Combinar fondo y texto
            video_segment = CompositeVideoClip([
                background_clip,
                txt_clip
            ]).set_audio(audio_clip)

            clips_finales.append(video_segment)
            time.sleep(0.2)

        # Añadir clip de suscripción (con fondo de video si es posible)
        subscribe_img = create_subscription_image(logo_url)
        subscribe_clip = ImageClip(subscribe_img).set_duration(5)
        clips_finales.append(subscribe_clip)

        # Concatenar todos los clips
        video_final = concatenate_videoclips(clips_finales, method="compose")

        video_final.write_videofile(
            nombre_salida,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            preset='ultrafast',
            threads=4,
            logger=None
        )

        # Cerrar y limpiar todos los recursos
        video_final.close()

        for clip in clips_audio:
            clip.close()

        for clip in clips_finales:
            clip.close()

        # Eliminar archivos temporales
        for temp_file in archivos_temp:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logging.error(f"Error al eliminar archivo temporal {temp_file}: {str(e)}")

        return True, "Video generado exitosamente"

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        # Cerrar y limpiar recursos en caso de error
        for clip in clips_audio:
            try:
                clip.close()
            except:
                pass

        for clip in clips_finales:
            try:
                clip.close()
            except:
                pass

        for temp_file in archivos_temp:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

        return False, str(e)


def main():
    st.title("Creador de Videos con Fondo Único")

    uploaded_file = st.file_uploader("Carga un archivo de texto", type="txt")
    video_fondo = st.file_uploader("Carga un video para el fondo (opcional)", type=["mp4", "mov", "avi"])
    voz_seleccionada = st.selectbox("Selecciona la voz", options=list(VOCES_DISPONIBLES.keys()))
    logo_url = "https://yt3.ggpht.com/pBI3iT87_fX91PGHS5gZtbQi53nuRBIvOsuc-Z-hXaE3GxyRQF8-vEIDYOzFz93dsKUEjoHEwQ=s176-c-k-c0x00ffffff-no-rj"  # Reemplaza con la URL de tu logo

    if uploaded_file:
        texto = uploaded_file.read().decode("utf-8")
        nombre_salida = st.text_input("Nombre del Video (sin extensión)", "video_generado")

        if st.button("Generar Video"):
            with st.spinner('Generando video...'):
                nombre_salida_completo = f"{nombre_salida}.mp4"
                success, message = create_simple_video_with_one_background(texto, nombre_salida_completo, voz_seleccionada, logo_url, video_fondo)

                if success:
                    st.success(message)
                    try:
                        st.video(nombre_salida_completo)
                        with open(nombre_salida_completo, 'rb') as file:
                            st.download_button(label="Descargar video", data=file, file_name=nombre_salida_completo)
                    except Exception as e:
                        st.error(f"Error al mostrar o descargar el video: {e}")
                else:
                    st.error(f"Error al generar video: {message}")



if __name__ == "__main__":
    main()
