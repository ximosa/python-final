import streamlit as st
import os
import logging
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import tempfile

logging.basicConfig(level=logging.INFO)

def create_text_image(text, size=(1280, 360), font_size=30, line_height=40, bg_color=(0, 0, 0, 180)):
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
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


def create_simplified_video(texto, nombre_salida, video_fondo):
    try:
        logging.info("Iniciando proceso de creación de video simplificado...")
        frases = [f.strip() for f in texto.split('.') if f.strip()]
        clips_finales = []

        # Cargar y preparar el video de fondo
        if video_fondo:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
                    tmp_file.write(video_fondo.read())
                    temp_video_path = tmp_file.name
                background_clip = VideoFileClip(temp_video_path, audio=False).resize(height=720)
            except Exception as e:
                logging.error(f"Error al cargar video de fondo: {str(e)}")
                return False, f"Error al cargar video de fondo: {str(e)}"
        else:
            logging.warning("No se ha cargado ningún video de fondo.")
            return False, "No se ha cargado ningún video de fondo."

        total_duration = 0
        for i, frase in enumerate(frases):
            total_duration += 3  # Duración arbitraria para cada frase

        # Hacer que el video de fondo dure todo el video
        if background_clip.duration < total_duration:
            n_loops = int(total_duration / background_clip.duration) + 1
            background_clip = background_clip.loop(n=n_loops).subclip(0, total_duration)
        else:
            background_clip = background_clip.subclip(0, total_duration)

        current_time = 0
        for i, frase in enumerate(frases):
            duracion = 3  # Duración arbitraria para cada frase

            # Crear capa de texto semi-transparente
            text_img = create_text_image(frase)
            txt_clip = (ImageClip(text_img)
                      .set_duration(duracion)
                      .set_position(('center', 'bottom'))
                      .set_start(current_time))

            # Combinar fondo y texto
            video_segment = CompositeVideoClip([
                background_clip.subclip(current_time, current_time + duracion),
                txt_clip
            ])
            clips_finales.append(video_segment)
            current_time += duracion

        # Concatenar todos los clips
        video_final = concatenate_videoclips(clips_finales, method="compose")

        # Escribir el archivo de video
        video_final.write_videofile(
            nombre_salida,
            fps=24,
            codec='libx264',
            audio_codec='aac',  # Mantener el codec de audio para que funcione la visualización
            preset='ultrafast',
            threads=4,
            logger=None
        )

        # Cerrar y limpiar todos los recursos
        video_final.close()
        background_clip.close()

        # Eliminar el video temporal de fondo
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)

        return True, "Video generado exitosamente"

    except Exception as e:
        logging.error(f"Error general: {str(e)}")
        return False, str(e)



def main():
    st.title("Creador de Videos Simplificado")

    uploaded_file = st.file_uploader("Carga un archivo de texto", type="txt")
    video_fondo = st.file_uploader("Carga un video para el fondo", type=["mp4", "mov", "avi"])

    if uploaded_file and video_fondo:  # Requerir ambos archivos
        texto = uploaded_file.read().decode("utf-8")
        nombre_salida = st.text_input("Nombre del Video (sin extensión)", "video_simplificado")

        if st.button("Generar Video"):
            with st.spinner('Generando video...'):
                nombre_salida_completo = f"{nombre_salida}.mp4"
                success, message = create_simplified_video(texto, nombre_salida_completo, video_fondo)

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
