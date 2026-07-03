import sys
from pathlib import Path

from sqlmodel import Session

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import create_db_and_tables, engine
from app.schemas import AssistantConfigIn
from app.services.assistant_manager import upsert_assistant


DEMO_CMID = 194522


def main() -> None:
    create_db_and_tables()
    payload = AssistantConfigIn(
        nombre="Calendario comunal EIB",
        descripcion_producto=(
            "El calendario comunal es una herramienta pedagogica fundamental en Educacion Inicial EIB "
            "para ambito rural. Organiza actividades socioculturales y socioproductivas de la comunidad, "
            "saberes asociados, problemas del contexto y aliados posibles. Sirve como insumo para una "
            "planificacion curricular pertinente y para promover dialogo de saberes."
        ),
        contexto_curso=(
            "Unidad 1, sesion 2: se aborda el calendario comunal como herramienta para recoger "
            "actividades socioculturales y socioproductivas, saberes comunitarios, problemas del "
            "contexto y aliados. Se relaciona con la planificacion curricular pertinente y el "
            "dialogo de saberes en Educacion Inicial EIB."
        ),
        ejemplo_producto=(
            "Ejemplo de referencia: un calendario organizado por epocas o meses, con columnas para "
            "actividades de la comunidad, saberes asociados, problemas o potencialidades, aliados y "
            "posibilidades pedagogicas. Debe evidenciar actividades como siembra, cosecha, festividades, "
            "preparacion de alimentos u otras practicas propias de la comunidad."
        ),
        analiza_texto=True,
        analiza_tablas=True,
        analiza_imagenes=False,
        usa_cmid_relacionado=False,
        cmid_relacionado=None,
        validar_documento=True,
        validar_similitud=True,
        rubrica=[
            {
                "dimension": "Estructura y organizacion del calendario comunal",
                "descripcion_dimension": (
                    "Evalua si el producto presenta una estructura clara, completa y organizada "
                    "segun los componentes esperados del calendario comunal."
                ),
                "criterio": "Presencia de las cinco columnas estructurales",
                "descripcion_criterio": (
                    "Verifica que el calendario incluya las columnas necesarias para organizar "
                    "epocas, actividades, saberes, problemas y aliados de la comunidad."
                ),
                "niveles": {
                    "inicio": "Carece de mas de dos columnas o las columnas no corresponden a las definidas.",
                    "en_proceso": "Tiene columnas basicas, pero algunas estan incompletas, fusionadas o mal nombradas.",
                    "logrado": "Las cinco columnas estan presentes, correctamente nombradas y con contenido.",
                    "destacado": "Las cinco columnas estan completas y agrega valor, como nomenclatura en lengua originaria.",
                },
            },
            {
                "dimension": "Estructura y organizacion del calendario comunal",
                "descripcion_dimension": (
                    "Evalua si el producto presenta una estructura clara, completa y organizada "
                    "segun los componentes esperados del calendario comunal."
                ),
                "criterio": "Organizacion temporal por epocas o ciclos comunales",
                "descripcion_criterio": (
                    "Revisa si las actividades estan ordenadas segun los tiempos, epocas o ciclos "
                    "reconocidos por la comunidad."
                ),
                "niveles": {
                    "inicio": "No organiza la informacion por epocas, meses o ciclos comunales.",
                    "en_proceso": "Presenta una organizacion temporal parcial o poco clara.",
                    "logrado": "Organiza las actividades segun epocas o ciclos comunales de manera comprensible.",
                    "destacado": "Relaciona ciclos comunales con actividades, saberes, senas y momentos pedagogicos.",
                },
            },
            {
                "dimension": "Estructura y organizacion del calendario comunal",
                "descripcion_dimension": (
                    "Evalua si el producto presenta una estructura clara, completa y organizada "
                    "segun los componentes esperados del calendario comunal."
                ),
                "criterio": "Presencia de matrices complementarias",
                "descripcion_criterio": (
                    "Verifica si el producto incorpora matrices o informacion complementaria que "
                    "ayude a profundizar problemas, potencialidades, aliados y saberes."
                ),
                "niveles": {
                    "inicio": "No incluye matrices complementarias ni informacion de soporte.",
                    "en_proceso": "Incluye matrices incompletas o sin relacion clara con el calendario.",
                    "logrado": "Incluye matrices complementarias pertinentes y vinculadas al calendario.",
                    "destacado": "Las matrices complementarias profundizan potencialidades, problemas, aliados y saberes.",
                },
            },
            {
                "dimension": "Actividades socioculturales y socioproductivas",
                "descripcion_dimension": (
                    "Evalua la pertinencia de las actividades seleccionadas y su relacion con la "
                    "vida cotidiana, cultural y productiva de la comunidad."
                ),
                "criterio": "Pertinencia y contextualizacion de las actividades",
                "descripcion_criterio": (
                    "Verifica que las actividades respondan al contexto real de la comunidad y no "
                    "sean ejemplos genericos o descontextualizados."
                ),
                "niveles": {
                    "inicio": "Las actividades son genericas o no reflejan el contexto de la comunidad.",
                    "en_proceso": "Incluye actividades del contexto, pero con poca descripcion o precision.",
                    "logrado": "Las actividades son pertinentes y reflejan practicas socioculturales y socioproductivas.",
                    "destacado": "Contextualiza actividades con saberes, ritos, senas, secretos, lengua y territorio.",
                },
            },
            {
                "dimension": "Actividades socioculturales y socioproductivas",
                "descripcion_dimension": (
                    "Evalua la pertinencia de las actividades seleccionadas y su relacion con la "
                    "vida cotidiana, cultural y productiva de la comunidad."
                ),
                "criterio": "Priorizacion pedagogica para el nivel inicial",
                "descripcion_criterio": (
                    "Revisa si las actividades seleccionadas pueden convertirse en situaciones "
                    "significativas adecuadas para ninos y ninas de Educacion Inicial."
                ),
                "niveles": {
                    "inicio": "No se evidencia vinculacion con necesidades pedagogicas de Educacion Inicial.",
                    "en_proceso": "La vinculacion pedagogica es general o insuficiente.",
                    "logrado": "Prioriza actividades viables para experiencias de aprendizaje en Inicial.",
                    "destacado": "Propone situaciones significativas claras y articulables con competencias del CNEB.",
                },
            },
            {
                "dimension": "Actividades socioculturales y socioproductivas",
                "descripcion_dimension": (
                    "Evalua la pertinencia de las actividades seleccionadas y su relacion con la "
                    "vida cotidiana, cultural y productiva de la comunidad."
                ),
                "criterio": "Equilibrio entre actividades socioproductivas y socioculturales",
                "descripcion_criterio": (
                    "Revisa si el calendario considera tanto actividades productivas como culturales, "
                    "evitando una seleccion limitada o poco variada."
                ),
                "niveles": {
                    "inicio": "Predomina un solo tipo de actividad o hay poca variedad.",
                    "en_proceso": "Hay ambos tipos de actividades, pero el equilibrio es limitado.",
                    "logrado": "Incluye actividades socioproductivas y socioculturales de manera equilibrada.",
                    "destacado": "Integra ambos tipos con problemas, potencialidades, aliados y saberes comunitarios.",
                },
            },
        ],
        perfil_retroalimentacion=[
            "Iniciar reconociendo aciertos y explicar por que son valiosos.",
            "Senalar omisiones o debilidades de manera especifica e indicar como incorporarlas.",
            "Relacionar observaciones con contenidos del curso y con la planificacion curricular pertinente.",
            "Proponer preguntas reflexivas que ayuden al docente a profundizar.",
            "Sugerir ejemplos concretos adaptados al contexto del docente.",
            "Recordar que el calendario comunal es una herramienta viva que puede actualizarse.",
            "Nunca emitir juicios de valor sobre la cultura o las practicas de la comunidad.",
            "Evitar comparaciones que jerarquicen comunidades.",
            "Fomentar articulacion con caracterizacion linguistica, tratamiento de lenguas y dialogo de saberes.",
        ],
    )

    with Session(engine) as session:
        upsert_assistant(session, DEMO_CMID, payload)

    print(f"Asistente demo creado para cmid={DEMO_CMID}")


if __name__ == "__main__":
    main()
