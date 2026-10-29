import ast
import math
import operator
import statistics as estadistica
from collections import Counter

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Calculadora científica",
    page_icon="🧮",
    layout="wide",
)

for clave, valor in {
    "expresion": "",
    "ultimo_resultado": 0.0,
    "resultado": None,
    "error": "",
    "historial": [],
}.items():
    if clave not in st.session_state:
        st.session_state[clave] = valor


def formato(numero):
    return f"{numero:.12g}"


# ============================================================
# EVALUADOR CIENTÍFICO
# ============================================================

def entero(valor):
    if not math.isfinite(valor) or valor < 0 or int(valor) != valor:
        raise ValueError("Se requiere un entero no negativo.")

    if valor > 1000:
        raise ValueError("El entero no puede superar 1000.")

    return int(valor)


def evaluar(expresion, modo, anterior):
    expresion = (
        expresion.strip()
        .replace("^", "**")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("π", "pi")
    )

    if not expresion:
        raise ValueError("Escribe una operación.")

    if len(expresion) > 500:
        raise ValueError("La expresión es demasiado larga.")

    grados = modo == "Grados"

    def convertir(x):
        return math.radians(x) if grados else x

    def convertir_inversa(x):
        return math.degrees(x) if grados else x

    def tangente(x):
        angulo = convertir(x)

        if abs(math.cos(angulo)) < 1e-12:
            raise ValueError("La tangente no está definida en ese ángulo.")

        return math.tan(angulo)

    funciones = {
        "sqrt": math.sqrt,
        "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
        "sin": lambda x: math.sin(convertir(x)),
        "cos": lambda x: math.cos(convertir(x)),
        "tan": tangente,
        "asin": lambda x: convertir_inversa(math.asin(x)),
        "acos": lambda x: convertir_inversa(math.acos(x)),
        "atan": lambda x: convertir_inversa(math.atan(x)),
        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,
        "ln": math.log,
        "log": math.log10,
        "logb": lambda x, base: math.log(x, base),
        "exp": math.exp,
        "abs": abs,
        "floor": math.floor,
        "ceil": math.ceil,
        "fact": lambda n: math.factorial(entero(n)),
        "comb": lambda n, k: math.comb(entero(n), entero(k)),
        "perm": lambda n, k: math.perm(entero(n), entero(k)),
        "hypot": math.hypot,
        "pct": lambda x: x / 100,
    }

    constantes = {
        "pi": math.pi,
        "e": math.e,
        "ans": anterior,
    }

    operaciones = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
    }

    arbol = ast.parse(expresion, mode="eval")

    if sum(1 for _ in ast.walk(arbol)) > 150:
        raise ValueError("La expresión es demasiado compleja.")

    def resolver(nodo):
        if isinstance(nodo, ast.Expression):
            return resolver(nodo.body)

        if isinstance(nodo, ast.Constant):
            if type(nodo.value) not in (int, float):
                raise ValueError("Solo se permiten números.")

            valor = float(nodo.value)

        elif isinstance(nodo, ast.Name):
            if nodo.id not in constantes:
                raise ValueError(f"Constante desconocida: {nodo.id}")

            valor = constantes[nodo.id]

        elif isinstance(nodo, ast.UnaryOp):
            numero = resolver(nodo.operand)

            if isinstance(nodo.op, ast.UAdd):
                valor = numero
            elif isinstance(nodo.op, ast.USub):
                valor = -numero
            else:
                raise ValueError("Operación no permitida.")

        elif isinstance(nodo, ast.BinOp):
            izquierda = resolver(nodo.left)
            derecha = resolver(nodo.right)

            if isinstance(nodo.op, ast.Pow):
                if abs(derecha) > 1000:
                    raise ValueError("El exponente no puede superar ±1000.")

                valor = izquierda ** derecha
            elif type(nodo.op) in operaciones:
                valor = operaciones[type(nodo.op)](izquierda, derecha)
            else:
                raise ValueError("Operación no permitida.")

        elif isinstance(nodo, ast.Call):
            if (
                not isinstance(nodo.func, ast.Name)
                or nodo.func.id not in funciones
                or nodo.keywords
            ):
                raise ValueError("Función no permitida.")

            argumentos = [resolver(arg) for arg in nodo.args]
            valor = funciones[nodo.func.id](*argumentos)

        else:
            raise ValueError("La expresión contiene elementos no permitidos.")

        if isinstance(valor, complex):
            raise ValueError("Esta calculadora trabaja con números reales.")

        if not math.isfinite(valor):
            raise ValueError("El resultado excede el rango permitido.")

        return valor

    return resolver(arbol)


# ============================================================
# ACCIONES DEL TECLADO
# ============================================================

def escribir(texto):
    st.session_state.expresion += texto
    st.session_state.error = ""


def limpiar():
    st.session_state.expresion = ""
    st.session_state.resultado = None
    st.session_state.error = ""


def borrar():
    st.session_state.expresion = st.session_state.expresion[:-1]


def calcular():
    try:
        expresion = st.session_state.expresion

        valor = evaluar(
            expresion,
            st.session_state.modo,
            st.session_state.ultimo_resultado,
        )

        st.session_state.resultado = valor
        st.session_state.ultimo_resultado = valor
        st.session_state.error = ""

        st.session_state.historial.insert(
            0,
            {
                "Operación": expresion,
                "Modo": st.session_state.modo,
                "Resultado": formato(valor),
            },
        )

        st.session_state.historial = st.session_state.historial[:100]

    except (
        ValueError,
        TypeError,
        SyntaxError,
        ZeroDivisionError,
        OverflowError,
        RecursionError,
    ) as error:
        st.session_state.error = f"No se pudo calcular: {error}"
        st.session_state.resultado = None


# ============================================================
# FUNCIONES ESTADÍSTICAS
# ============================================================

def percentil(ordenados, porcentaje):
    posicion = (len(ordenados) - 1) * porcentaje / 100
    inferior = math.floor(posicion)
    superior = math.ceil(posicion)
    fraccion = posicion - inferior

    return (
        ordenados[inferior] * (1 - fraccion)
        + ordenados[superior] * fraccion
    )


def analizar_datos(texto, tipo):
    partes = texto.replace(";", " ").split()

    if not partes:
        raise ValueError("Ingresa al menos un dato.")

    if len(partes) > 10000:
        raise ValueError("Puedes ingresar hasta 10 000 datos.")

    datos = [float(p.replace(",", ".")) for p in partes]

    if not all(math.isfinite(x) for x in datos):
        raise ValueError("Todos los datos deben ser números finitos.")

    n = len(datos)
    ordenados = sorted(datos)
    media = estadistica.mean(datos)
    mediana = estadistica.median(datos)

    frecuencias = Counter(datos)
    frecuencia_maxima = max(frecuencias.values())

    if frecuencia_maxima == 1:
        moda = "Sin moda: todos aparecen una vez"
    elif len(frecuencias) > 1 and len(set(frecuencias.values())) == 1:
        moda = "Sin moda predominante"
    else:
        modas = sorted(
            valor
            for valor, frecuencia in frecuencias.items()
            if frecuencia == frecuencia_maxima
        )
        moda = ", ".join(formato(x) for x in modas)

    if tipo == "Muestra" and n < 2:
        varianza = None
        desviacion = None
    elif tipo == "Muestra":
        varianza = estadistica.variance(datos)
        desviacion = estadistica.stdev(datos)
    else:
        varianza = estadistica.pvariance(datos)
        desviacion = estadistica.pstdev(datos)

    q1 = percentil(ordenados, 25)
    q3 = percentil(ordenados, 75)

    filas = [
        ("Cantidad de datos", str(n)),
        ("Suma", formato(math.fsum(datos))),
        ("Media", formato(media)),
        ("Mediana", formato(mediana)),
        ("Moda", moda),
        ("Mínimo", formato(min(datos))),
        ("Máximo", formato(max(datos))),
        ("Rango", formato(max(datos) - min(datos))),
        ("Primer cuartil Q1", formato(q1)),
        ("Tercer cuartil Q3", formato(q3)),
        ("Rango intercuartílico", formato(q3 - q1)),
        (
            "Varianza",
            formato(varianza) if varianza is not None
            else "Se requieren al menos 2 datos",
        ),
        (
            "Desviación estándar",
            formato(desviacion) if desviacion is not None
            else "Se requieren al menos 2 datos",
        ),
    ]

    if desviacion is not None and media > 0:
        cv = f"{formato(desviacion / media * 100)} %"
    else:
        cv = "Requiere media positiva y desviación disponible"

    filas.append(("Coeficiente de variación", cv))

    if all(x > 0 for x in datos):
        filas.extend([
            ("Media geométrica", formato(estadistica.geometric_mean(datos))),
            ("Media armónica", formato(estadistica.harmonic_mean(datos))),
        ])
    else:
        filas.extend([
            ("Media geométrica", "Requiere datos positivos"),
            ("Media armónica", "Requiere datos positivos"),
        ])

    resultados = pd.DataFrame(
        filas,
        columns=["Medida estadística", "Resultado"],
    )

    tabla_frecuencias = pd.DataFrame(
        sorted(frecuencias.items()),
        columns=["Valor", "Frecuencia"],
    )
    tabla_frecuencias["Frecuencia relativa (%)"] = (
        tabla_frecuencias["Frecuencia"] / n * 100
    )

    return datos, media, mediana, resultados, tabla_frecuencias


# ============================================================
# INTERFAZ WEB
# ============================================================

st.title("🧮 Calculadora científica y estadística")
st.caption("Operaciones científicas y análisis descriptivo de datos.")

tab_cientifica, tab_estadistica, tab_ayuda = st.tabs(
    ["Científica", "Estadística", "Ayuda"]
)


# ---------------- CALCULADORA CIENTÍFICA ----------------

with tab_cientifica:
    izquierda, derecha = st.columns([3, 2])

    with izquierda:
        st.radio(
            "Unidad de los ángulos",
            ["Grados", "Radianes"],
            horizontal=True,
            key="modo",
        )

        st.text_input(
            "Escribe una operación",
            key="expresion",
            placeholder="Ejemplo: sqrt(144) + sin(30)",
        )

        st.caption(
            "Los botones añaden texto al final de la expresión. "
            "Usa punto para los decimales."
        )

        teclado = [
            ["sin(", "cos(", "tan(", "(", ")", "C"],
            ["asin(", "acos(", "atan(", "sqrt(", "^", "⌫"],
            ["ln(", "log(", "exp(", "7", "8", "9"],
            ["fact(", "comb(", "perm(", "4", "5", "6"],
            ["pi", "e", "ans", "1", "2", "3"],
            ["abs(", "logb(", ",", "0", ".", "="],
            ["+", "-", "*", "/", "%", "pct("],
        ]

        for fila, botones in enumerate(teclado):
            columnas = st.columns(6)

            for columna, texto in enumerate(botones):
                if texto == "C":
                    accion, argumentos = limpiar, ()
                elif texto == "⌫":
                    accion, argumentos = borrar, ()
                elif texto == "=":
                    accion, argumentos = calcular, ()
                else:
                    accion, argumentos = escribir, (texto,)

                columnas[columna].button(
                    texto,
                    key=f"boton_{fila}_{columna}",
                    on_click=accion,
                    args=argumentos,
                    use_container_width=True,
                )

        if st.session_state.error:
            st.error(st.session_state.error)

        if st.session_state.resultado is not None:
            st.success(
                f"Resultado: {formato(st.session_state.resultado)}"
            )

    with derecha:
        st.subheader("Historial")

        if st.session_state.historial:
            st.dataframe(
                pd.DataFrame(st.session_state.historial),
                hide_index=True,
                use_container_width=True,
            )

            st.button(
                "Borrar historial",
                on_click=lambda: st.session_state.update(historial=[]),
            )
        else:
            st.info("Tus operaciones aparecerán aquí.")

        st.metric(
            "Último resultado · ans",
            formato(st.session_state.ultimo_resultado),
        )


# ---------------- ESTADÍSTICA ----------------

with tab_estadistica:
    st.subheader("Análisis estadístico descriptivo")

    st.write(
        "Separa los datos con espacios, saltos de línea o punto y coma. "
        "Puedes usar punto o coma decimal."
    )

    texto_datos = st.text_area(
        "Datos",
        value="12 15 18 12 20 22 15 18 19 21 25 15",
        height=130,
    )

    tipo = st.radio(
        "Los datos representan una:",
        ["Muestra", "Población"],
        horizontal=True,
    )

    st.caption(
        "Los resultados se actualizan al confirmar los cambios del campo."
    )

    try:
        datos, media, mediana, resultados, frecuencias = analizar_datos(
            texto_datos, tipo
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Cantidad de datos", len(datos))
        c2.metric("Media", formato(media))
        c3.metric("Mediana", formato(mediana))

        tabla, grafico = st.columns([3, 2])

        with tabla:
            st.subheader("Resultados")
            st.caption(f"Cálculo para: {tipo.lower()}")

            st.dataframe(
                resultados,
                hide_index=True,
                use_container_width=True,
            )

            st.download_button(
                "Descargar resultados en CSV",
                data=resultados.to_csv(index=False).encode("utf-8-sig"),
                file_name="resultados_estadisticos.csv",
                mime="text/csv",
            )

        with grafico:
            st.subheader("Frecuencias")

            if len(frecuencias) <= 100:
                st.bar_chart(
                    frecuencias.set_index("Valor")[["Frecuencia"]]
                )
            else:
                st.info(
                    "Hay más de 100 valores distintos. "
                    "Consulta la tabla de frecuencias."
                )

            st.dataframe(
                frecuencias,
                hide_index=True,
                use_container_width=True,
            )

        st.caption(
            "Varianza poblacional: divisor n. "
            "Varianza muestral: divisor n−1. "
            "Cuartiles: interpolación lineal."
        )

        st.info(
            "El coeficiente de variación es apropiado para variables "
            "con cero real y media positiva, como pesos, longitudes "
            "o tiempos."
        )

    except (ValueError, OverflowError, estadistica.StatisticsError) as error:
        st.error(f"No se pudieron analizar los datos: {error}")


# ---------------- AYUDA ----------------

with tab_ayuda:
    st.subheader("Ejemplos de operaciones")

    st.table(pd.DataFrame([
        ("sqrt(144)", "Raíz cuadrada"),
        ("cbrt(27)", "Raíz cúbica"),
        ("2^8", "Potencia"),
        ("sin(30)", "Seno; selecciona Grados"),
        ("asin(0.5)", "Arcoseno"),
        ("ln(e)", "Logaritmo natural"),
        ("log(100)", "Logaritmo en base 10"),
        ("logb(8,2)", "Logaritmo en otra base"),
        ("fact(5)", "Factorial"),
        ("comb(10,3)", "Combinaciones"),
        ("perm(10,3)", "Permutaciones"),
        ("250*pct(18)", "18 % de 250"),
        ("10%3", "Resto de la división"),
        ("ans*2", "Multiplicar el último resultado por 2"),
        ("hypot(3,4)", "Hipotenusa"),
    ], columns=["Expresión", "Descripción"]))

    st.markdown(
        """
- Escribe las multiplicaciones con `*`: por ejemplo, `2*pi`.
- En la calculadora científica usa **punto decimal**: `2.5`.
- La coma separa argumentos: `comb(10,3)`.
- En estadística, separa datos con espacios o `;`: `10 12,5 15`.
- La calculadora trabaja con **números reales**.
- El historial se conserva durante la sesión del navegador.
        """
    )