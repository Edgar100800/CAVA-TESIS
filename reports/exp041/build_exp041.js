const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  AlignmentType, HeadingLevel, LevelFormat, ShadingType, BorderStyle, Footer,
  PageNumber, TableOfContents, PageBreak,
} = require("docx");

const FONT = "Arial";
const W = 9638; // A4 width minus 2 cm margins, in DXA
const ACCENT = "1F4E79";
const HEAD_FILL = "DCE6F1";
const NOTE_FILL = "F3F6FA";

// **bold** and _italic_ inline markup
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|_[^_]+_)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const P = (t, opts = {}) => new Paragraph({ children: runs(t), spacing: { after: 120 }, ...opts });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const B = (t, level = 0) => new Paragraph({ numbering: { reference: "bullets", level }, children: runs(t), spacing: { after: 60 } });
const N = (t, ref = "nums") => new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(t), spacing: { after: 60 } });
const note = (t) => new Paragraph({
  children: runs(t, { size: 19 }),
  shading: { type: ShadingType.CLEAR, fill: NOTE_FILL, color: "auto" },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 6 } },
  spacing: { before: 60, after: 160 }, indent: { left: 120 },
});

function cell(text, width, header = false) {
  const paras = String(text).split("\n").map((line) => new Paragraph({
    children: runs(line, header ? { bold: true, size: 19 } : { size: 19 }),
    spacing: { after: 40 },
  }));
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: HEAD_FILL, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: paras,
  });
}
function table(headers, rows, fractions) {
  const widths = fractions.map((f) => Math.round(f * W));
  widths[widths.length - 1] = W - widths.slice(0, -1).reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "A6A6A6" };
  return new Table({
    width: { size: W, type: WidthType.DXA },
    columnWidths: widths,
    borders: { top: border, bottom: border, left: border, right: border, insideHorizontal: border, insideVertical: border },
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i])) })),
    ],
  });
}
const gap = () => new Paragraph({ children: [], spacing: { after: 80 } });

// ---------------------------------------------------------------- content
const c = [];

// Title block
c.push(new Paragraph({ children: [new TextRun({ text: "CAVA · Evaluación con usuarios", font: FONT, size: 22, color: ACCENT, bold: true })], spacing: { after: 60 } }));
c.push(new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun("EXP-041 · ¿Representan las secciones de CAVA la historia de una película?")] }));
c.push(new Paragraph({ children: runs("Protocolo de la evaluación con estudiantes UTEC sobre _Spider-Man: Brand New Day_ (2026)", { size: 24, color: "404040" }), spacing: { after: 200 } }));
c.push(table(["Campo", "Valor"], [
  ["Estado", "Borrador del pre-registro. Se firma en docs/EXPERIMENT_LOG.md **antes del piloto** y no se modifica después de recolectar el primer juicio."],
  ["Experimento hermano", "EXP-040 (videos de YouTube del conjunto propio). Corre en paralelo, con su propio pre-registro y su propio análisis."],
  ["Película", "_Spider-Man: Brand New Day_ (2026), 145 min, audio en inglés."],
  ["Sistemas comparados", "CAVA (producto congelado) · U (sin estructura) · S (solo señal visual)."],
  ["Participantes", "Estudiantes UTEC mayores de 18 años que ya vieron la película. Meta: 60; mínimo: 40."],
  ["Duración por sesión", "100 minutos, en sala de cómputo con audífonos."],
], [0.25, 0.75]));
c.push(gap());
c.push(new Paragraph({ children: [new PageBreak()] }));

// 1
c.push(H1("1. Resumen"));
c.push(P("Las referencias automáticas que usamos hasta ahora (importancia humana de TVSum y SumMe, capítulos de autor) no distinguen a CAVA de selecciones simples, y tienen sesgos propios como la posición dentro del video (EXP-031, 032, 037, 038). La medición que falta es la de personas."));
c.push(P("En esta evaluación, estudiantes que ya vieron _Spider-Man: Brand New Day_ hacen tres cosas, en este orden:"));
c.push(N("**Recuerdan** la película sin ver nada: escriben y marcan en una cuadrícula neutral los momentos que no pueden faltar en un resumen. Esto construye la referencia humana de la película, del mismo tipo que la de TVSum."));
c.push(N("**Comparan a ciegas** pares de versiones del mismo formato (línea de tiempo por capítulos y highlights de 4 minutos): CAVA frente a una selección sin estructura (U) y frente a la mejor señal sola (S)."));
c.push(N("**Ven la demostración** de CAVA, con las secciones organizadas según el storyline de la película, y conversan en un grupo focal. La demostración va al final para no condicionar los juicios."));
c.push(note("**Qué se puede afirmar con este diseño:** qué tan bien representan las versiones la historia, según personas que ya la conocen. **Qué no se puede afirmar:** retención o aprendizaje de alguien que no vio la película, ni generalización a otras películas (hay una sola)."));

// 2
c.push(H1("2. Objetivo y preguntas de investigación"));
c.push(P("**Objetivo.** Medir si las secciones que CAVA selecciona de una película representan su historia mejor que una selección sin estructura con el mismo presupuesto, según personas que ya la vieron; y construir una referencia humana de los momentos esenciales de la película que se pueda comparar con TVSum y SumMe usando las mismas métricas."));
c.push(table(["#", "Pregunta", "Cómo se responde", "Tipo"], [
  ["PI1", "¿Las personas prefieren la línea de tiempo por capítulos de CAVA frente a la de U?", "Elección a ciegas en el par T (bloque C)", "Principal, con criterio"],
  ["PI2", "¿Prefieren los highlights de 4 min de CAVA frente a los de U?", "Elección a ciegas en el par H (bloque C)", "Principal, con criterio"],
  ["PI3", "¿Los highlights de CAVA cubren más momentos esenciales de cada persona que los de U?", "Cobertura de las marcas del bloque B", "Secundaria, con criterio"],
  ["PI4", "¿CAVA supera a la mejor señal sola (S)?", "Par S (bloque C)", "Secundaria, informativa"],
  ["PI5", "¿Qué formato usarían y qué falta para que sea útil?", "Bloques D y E", "Cualitativa"],
], [0.07, 0.43, 0.3, 0.2]));

// 3
c.push(H1("3. Relación con EXP-040"));
c.push(B("**EXP-040** mide preferencia sobre los 9 videos de YouTube del conjunto propio (educativo, español e inglés), con los cinco formatos del producto. Generaliza sobre videos."));
c.push(B("**EXP-041** (este documento) mide una película con personas que la conocen y añade la referencia humana de recuerdo. Generaliza sobre personas, no sobre películas."));
c.push(B("Se ejecutan en paralelo con la misma plataforma de juicios, pero los juicios, los criterios y los análisis no se mezclan. Si una persona participa en los dos, se registra con el mismo código y se analiza en cada experimento por separado."));
c.push(B("El pre-registro de EXP-040 está escrito pero **aún no está en el historial de git**. Hay que confirmarlo con un commit antes de recolectar cualquier juicio de cualquiera de los dos experimentos."));

// 4
c.push(H1("4. Material"));
c.push(H2("4.1 Película y corrida de CAVA"));
c.push(table(["Dato", "Valor"], [
  ["Película", "_Spider-Man: Brand New Day_ (2026), 145 min (8 700 s)"],
  ["Pistas del archivo", "Audio en inglés (además de hindi, tamil y telugu). Subtítulos en inglés (normal y SDH). **No hay audio en español.**"],
  ["Corrida", "data/films_runs/Spider_Man, perfil film, G-versión verdadera"],
  ["Mapa de tópicos", "1 740 unidades de 5 s · 104 tópicos en el nivel default, 45 con retornos, duración mediana 37,5 s · 8 grupos de voz (V1–V8)"],
], [0.25, 0.75]));
c.push(H2("4.2 Sistemas comparados"));
c.push(P("Los tres sistemas usan la misma maquinaria: unidades de 5 s, el mismo corte y codificación, el mismo presupuesto por formato y el mismo modelo de etiquetas (Qwen2.5-14B). Solo cambia qué tramos se eligen. Es la misma definición de EXP-040 (scripts/exp040_baselines.py), aplicada al perfil film."));
c.push(table(["Sistema", "Línea de tiempo (capítulos)", "Highlights 4 min"], [
  ["**CAVA**", "Un capítulo por tópico del mapa multimodal, con su etiqueta", "Tramos de los tópicos principales del mapa"],
  ["**U · sin estructura**", "Cortes equiespaciados, el mismo número de capítulos que CAVA, etiquetados por el mismo modelo", "Clips equiespaciados con las mismas duraciones que los de CAVA"],
  ["**S · mejor señal sola**", "Mapa con solo la señal visual (mismos percentiles del perfil, sin snap), mismo código de versiones", "Misma regla de CAVA sobre el mapa visual"],
], [0.22, 0.42, 0.36]));
c.push(H2("4.3 Formatos que se evalúan"));
c.push(table(["Formato", "Cómo se presenta", "Límite de tiempo por versión", "Decisión"], [
  ["**T · Línea de tiempo por capítulos**", "Barra de 145 min con bloques por capítulo, etiqueta al pasar el cursor y miniatura; un clic reproduce el clip del capítulo", "3 min", "Se evalúa"],
  ["**H · Highlights de 4 min**", "Video continuo de 240 s con su barra de clips", "4 min (todo el video)", "Se evalúa"],
  ["Recap 60 s", "—", "—", "Fuera: un solo clip de 60 s no representa 145 min"],
  ["Hilos de tópico", "—", "—", "Fuera: 7–11 min por hilo, no cabe en la sesión"],
  ["Hilos por hablante", "—", "—", "Fuera: las voces V1–V8 no tienen nombre y no deben presentarse como personajes"],
  ["Capítulos como video", "—", "—", "Fuera: 67 min de clips; se muestra como línea de tiempo"],
], [0.24, 0.38, 0.18, 0.2]));
c.push(note("**Cambio declarado respecto al producto:** los highlights del producto usan el 10 % de la duración (14,5 min en esta película). Para el evento, los tres sistemas usan un presupuesto fijo de **240 s**, con el mismo código de versiones y G-versión. Es un cambio de parámetro, no de código, y se registra en el pre-registro."));
c.push(H2("4.4 Cuadrícula neutral para el recuerdo"));
c.push(P("Una miniatura cada 90 s (97 imágenes), con su minuto, en filas de 10 minutos. No se deriva de ningún sistema, así que no favorece a CAVA, U ni S. Sirve para ubicar en el tiempo los momentos que cada persona recuerda."));
c.push(H2("4.5 Idioma"));
c.push(B("Audio original en inglés con subtítulos en inglés quemados, idénticos en todas las versiones."));
c.push(B("Las etiquetas de capítulo se muestran tal como las genera el modelo (en inglés), iguales para los tres sistemas. Si se decide traducirlas, se traducen con el mismo procedimiento automático para los tres, sin edición manual, y se declara antes del piloto."));
c.push(B("El filtro (bloque A) mide la comprensión del inglés hablado para analizarla como moderador."));

// 5
c.push(H1("5. Participantes y convocatoria"));
c.push(H2("5.1 Criterios"));
c.push(B("**Inclusión:** estudiante UTEC, 18 años o más, que vio _Spider-Man: Brand New Day_ al menos una vez."));
c.push(B("Quien no la vio puede asistir a la demostración y, si se corre en paralelo, participar en EXP-040; no participa en los bloques B a D de EXP-041."));
c.push(B("**Exclusión de análisis** (pre-declarada): ver sección 9.4."));
c.push(H2("5.2 Tamaño de muestra"));
c.push(P("Con una sola película, cada formato tiene exactamente una versión de CAVA y una de U, así que todas las personas juzgan el mismo par. Cada persona aporta **un juicio independiente por formato** y la prueba es binomial sobre personas, sin necesidad de agrupar. El efecto mínimo detectable (α 0,05 bilateral, potencia 0,8, sin contar empates) es:"));
c.push(table(["Juicios sin empate por formato", "Preferencia mínima detectable"], [
  ["29", "75 / 25"],
  ["47", "70 / 30"],
  ["62", "67,5 / 32,5"],
  ["85", "65 / 35"],
], [0.5, 0.5]));
c.push(P("**Meta:** 60 participantes que vieron la película, en dos sesiones de unos 30 (según la capacidad de la sala). **Mínimo:** 40. Se declara de antemano que una preferencia menor a ~70/30 puede no detectarse."));
c.push(H2("5.3 Convocatoria (texto para Freshit y redes)"));
c.push(note("**¿Viste Spider-Man: Brand New Day?** Te invitamos a una sesión de 100 minutos en la que compararás resúmenes automáticos de la película y conocerás un sistema de resumen de video desarrollado en UTEC. Entre quienes completen la sesión sortearemos 5 vales de consumo. Inscríbete aquí: [enlace]. Requisito: haber visto la película."));
c.push(P("El texto dice «resúmenes automáticos» y no «nuestro modelo»: las dos versiones de cada par son automáticas (también U), y así no se induce a elegir una."));
c.push(H2("5.4 Incentivo y datos personales"));
c.push(B("Cinco vales sorteados entre quienes completen la sesión. El sorteo no depende de las respuestas."));
c.push(B("Cada persona recibe un código (P001, P002…) que es lo único que se guarda junto a sus respuestas. Nombre y correo para el sorteo van en un formulario separado, que no se cruza con los datos."));

// 6
c.push(H1("6. Procedimiento de la sesión"));
c.push(table(["Hora", "Bloque", "Qué pasa", "Min"], [
  ["0:00", "A · Registro", "Bienvenida, consentimiento, código y filtro", "10"],
  ["0:10", "B · Recuerdo", "Sin ver ningún clip: sinopsis propia, 5–8 momentos esenciales y su ubicación en la cuadrícula", "15"],
  ["0:25", "C · Comparaciones", "Cuatro pares a ciegas: T, H, par de control y par S", "40"],
  ["1:05", "D · Cierre", "Preferencias de formato y comentarios", "10"],
  ["1:15", "—", "Se bloquean todas las respuestas de A a D", "5"],
  ["1:20", "E · Demostración y grupo focal", "CAVA por storyline, valoración por momento y conversación guiada; sorteo", "20"],
], [0.08, 0.22, 0.62, 0.08]));
c.push(P("Antes de la primera sesión se hace un **piloto con 3 personas** ajenas al equipo. Cualquier cambio que el piloto obligue se firma en el pre-registro antes de recolectar juicios de las demás."));

// 7
c.push(H1("7. Instrumento: preguntas"));
c.push(P("Todas las preguntas se presentan en la plataforma de juicios. Las escalas de acuerdo van de 1 (totalmente en desacuerdo) a 5 (totalmente de acuerdo)."));
c.push(H2("Bloque A · Registro y filtro"));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["A1", "Código de participante", "Asignado por el sistema"],
  ["A2", "Carrera y ciclo", "Lista"],
  ["A3", "Rango de edad", "18–20 · 21–23 · 24–26 · 27 o más"],
  ["A4", "¿Viste _Spider-Man: Brand New Day_?", "No · Sí, una vez · Sí, más de una vez"],
  ["A5", "¿Cuándo la viste por última vez?", "Hace menos de 1 mes · 1 a 3 meses · más de 3 meses"],
  ["A6", "¿En qué idioma la viste?", "Doblada al español · En inglés con subtítulos · En inglés sin subtítulos"],
  ["A7", "¿Qué tanto entiendes el inglés hablado en una película?", "1 (casi nada) a 5 (todo)"],
  ["A8", "¿Qué tanto recuerdas la historia?", "1 (muy poco) a 5 (casi todo)"],
  ["A9", "¿Con qué frecuencia ves resúmenes, recaps o explicaciones de películas (YouTube, TikTok)?", "Nunca · A veces · Frecuentemente"],
  ["A10", "Consentimiento informado", "Acepto / No acepto"],
], [0.07, 0.55, 0.38]));
c.push(H2("Bloque B · Recuerdo libre (antes de ver cualquier clip)"));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["B1", "En una o dos frases, ¿de qué trata la película?", "Texto"],
  ["B2", "Escribe, en orden, entre 5 y 8 momentos que no pueden faltar en un resumen de la película.", "Lista de textos"],
  ["B3", "En la cuadrícula, marca la imagen donde ocurre cada uno de esos momentos. Si no lo ubicas, déjalo sin marcar.", "Hasta 8 miniaturas, cada una ligada a un ítem de B2"],
], [0.07, 0.63, 0.3]));
c.push(H2("Bloque C · Comparaciones a ciegas"));
c.push(P("Cada par muestra las versiones A y B, del mismo formato, lado a lado. La persona no sabe qué sistema produjo cada una. Antes de responder debe haber abierto las dos."));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["C1", "¿Cuál de las dos versiones representa mejor la película?", "A · B · Iguales"],
  ["C2", "¿Qué tan seguro estás de tu elección?", "Poco · Algo · Muy seguro"],
  ["C3a", "Incluye los momentos que considero esenciales.", "1–5, para A y para B"],
  ["C3b", "Se entiende la secuencia de la historia, sin saltos que confundan.", "1–5, para A y para B"],
  ["C3c", "No incluye partes irrelevantes (créditos, logos, relleno).", "1–5, para A y para B"],
  ["C3d", "Los títulos describen bien lo que pasa en cada sección. **(solo línea de tiempo)**", "1–5, para A y para B"],
  ["C3e", "Se lo mostraría a alguien que no vio la película para que entienda de qué trata.", "1–5, para A y para B"],
  ["C4", "¿Qué momento esencial faltó? ¿Qué parte sobraba? (opcional)", "Texto"],
], [0.07, 0.63, 0.3]));
c.push(H2("Bloque D · Cierre"));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["D1", "Si tuvieras que recordar una película antes de ver su secuela, ¿qué usarías?", "Línea de tiempo con capítulos · Video de highlights · Un video resumen de YouTube · Volvería a ver la película · Nada"],
  ["D2", "¿En qué situación usarías una línea de tiempo con capítulos de una película?", "Texto"],
  ["D3", "¿Qué les falta a estas versiones para que te sean útiles?", "Texto"],
  ["D4", "En general, ¿qué tan útil te parece un sistema que resuma películas de esta manera?", "1 (nada útil) a 5 (muy útil)"],
], [0.07, 0.5, 0.43]));
c.push(H2("Bloque E · Demostración de CAVA por storyline y grupo focal"));
c.push(P("Después de bloquear las respuestas, se presenta CAVA abiertamente: el storyline de la película, momento por momento, con las secciones que CAVA asocia a cada uno. No es parte de la comparación a ciegas; sus datos son descriptivos."));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["E1", "Para cada uno de 5 momentos del storyline: ¿la sección mostrada corresponde a este momento de la historia?", "Sí · En parte · No"],
  ["E2", "¿Qué les sorprendió de las secciones que eligió el sistema?", "Conversación"],
  ["E3", "¿Qué momentos esperaban ver y no aparecieron?", "Conversación"],
  ["E4", "¿Confiarían en este tipo de resumen para decidir si ver una película o para recordarla antes de una secuela? ¿Por qué?", "Conversación"],
  ["E5", "¿Qué cambiarían de la forma de presentarlo: línea de tiempo, video, storyline?", "Conversación"],
], [0.07, 0.63, 0.3]));
c.push(note("**Requisito de la demostración:** hoy la capa narrativa solo acepta un guion ya alineado en el tiempo (t0, t1) y sus trabajos en GPU no han corrido (61386, 61784 y 61394, pendientes desde el 7 de noviembre). Para mostrar «storyline → secciones» hace falta congelar ese paso antes del evento y declarar de dónde sale el storyline (por ejemplo, una sinopsis pública escrita por el equipo antes de ver las salidas). Si no está listo, la demostración muestra el mapa de tópicos y la línea de tiempo de CAVA."));

// 8
c.push(H1("8. Asignación y contrabalanceo"));
c.push(P("Cada persona juzga cuatro pares. Los dos pares principales (T y H) van en las posiciones 1 y 3; el par de control en la 2; el par S al final, porque es secundario. Lado de CAVA y orden de formatos se contrabalancean con cuatro secuencias asignadas por turno según el código."));
c.push(table(["Secuencia", "Par 1", "Par 2", "Par 3", "Par 4"], [
  ["1", "T · CAVA a la izquierda", "Control", "H · CAVA a la derecha", "S en línea de tiempo"],
  ["2", "H · CAVA a la izquierda", "Control", "T · CAVA a la derecha", "S en highlights"],
  ["3", "T · CAVA a la derecha", "Control", "H · CAVA a la izquierda", "S en highlights"],
  ["4", "H · CAVA a la derecha", "Control", "T · CAVA a la izquierda", "S en línea de tiempo"],
], [0.14, 0.24, 0.12, 0.26, 0.24]));
c.push(B("**Par de control:** dos líneas de tiempo idénticas (CAVA contra CAVA), con 90 s por lado. La respuesta esperada es «Iguales»."));
c.push(B("En el par S, el lado de CAVA también se aleatoriza."));
c.push(B("Tiempos estimados: T 7,5 min, H 9,5 min, control 4 min, S 8–9,5 min; unos 35 min más transiciones."));

// 9
c.push(H1("9. Datos que se recolectan y análisis"));
c.push(H2("9.1 Datos"));
c.push(table(["Dato", "Origen", "Uso"], [
  ["Respuestas del filtro (A2–A9)", "Bloque A", "Elegibilidad y moderadores"],
  ["Sinopsis y lista de momentos (B1, B2)", "Bloque B", "Análisis cualitativo; correspondencia con el storyline"],
  ["Marcas en la cuadrícula con su minuto (B3)", "Bloque B", "Referencia humana: curva de momentos esenciales y cobertura"],
  ["Elección, seguridad, escalas y texto por par (C1–C4)", "Bloque C", "Criterios principales y secundarios"],
  ["Secuencia, lado de cada sistema y orden", "Plataforma", "Control del contrabalanceo"],
  ["Telemetría: tiempo por versión, reproducciones, saltos, % visto, tiempo hasta decidir", "Plataforma", "Exclusiones y esfuerzo por versión"],
  ["Preferencias de formato y utilidad (D1–D4)", "Bloque D", "Informativo"],
  ["Valoración por momento del storyline (E1)", "Bloque E", "Descriptivo, no ciego"],
  ["Notas del grupo focal (E2–E5)", "Moderador", "Cualitativo"],
], [0.42, 0.18, 0.4]));
c.push(H2("9.2 Criterios principales (por formato, sin empates)"));
c.push(N("**T:** proporción de personas que prefieren CAVA frente a U en la línea de tiempo. Prueba binomial exacta bilateral, IC 95 % de Clopper-Pearson. **Cumple** si la proporción es mayor a 0,50 y el IC no incluye 0,50.", "crit"));
c.push(N("**H:** lo mismo para los highlights de 4 min.", "crit"));
c.push(H2("9.3 Secundarios"));
c.push(N("**Cobertura de momentos esenciales (con criterio).** Para cada persona i, cobertura_i(v) es la fracción de sus marcas de B3 cuyo intervalo de 90 s se cruza con algún clip de los highlights v. Se compara CAVA con U de forma pareada sobre personas. **Cumple** si la diferencia media es mayor a 2 errores estándar.", "crit"));
c.push(N("**Curva humana estilo TVSum (informativo).** La fracción de personas que marcó cada celda forma una curva de importancia; se calcula la recompensa z de cada versión, igual que en EXP-031, para CAVA, U, S, 1 000 selecciones al azar con los mismos clips, y el **techo humano**: para cada persona, una selección construida con las marcas de las demás, con el mismo número y duración de clips que CAVA.", "crit"));
c.push(N("**CAVA frente a S (informativo):** misma prueba que 9.2, con menos juicios (la mitad de las personas por formato).", "crit"));
c.push(N("**Escalas C3:** diferencia pareada A−B por ítem (prueba de rangos con signo de Wilcoxon), tasa de «Iguales», relación con la seguridad (C2) y con la familiaridad (A4, A5, A8) y el inglés (A7).", "crit"));
c.push(H2("9.4 Exclusiones (pre-declaradas)"));
c.push(B("Quien elige A o B en el par de control: se excluyen todos sus juicios del bloque C (se reporta cuántos)."));
c.push(B("Un par en el que alguna versión se vio menos de 30 s: se excluye ese par."));
c.push(B("Menos de 3 marcas válidas en B3: se excluye solo del análisis de cobertura."));
c.push(B("Quien no vio la película (A4 = No): no entra en B–D."));
c.push(H2("9.5 Lecturas declaradas antes de ver los datos"));
c.push(B("**CAVA > U en T y en H:** la estructura multimodal aporta valor percibido en los dos formatos para esta película."));
c.push(B("**CAVA > U solo en T:** la estructura ayuda a navegar pero no a elegir los mejores momentos (coherente con EXP-031 y 037, donde la selección de highlights no superó a lo uniforme)."));
c.push(B("**CAVA ≈ U (IC incluye 0,50):** con este tamaño de muestra no se detecta preferencia; se reporta el efecto mínimo detectable."));
c.push(B("**CAVA < U:** la estructura daña la representación en ese formato; se revisan los comentarios de C4 y la cobertura."));
c.push(B("**Expectativa declarada:** CAVA > U en T; incertidumbre en H."));
c.push(B("**Adopción:** ningún resultado cambia el producto en esta tanda. Es la medición de cierre del sistema congelado."));

// 10
c.push(H1("10. Comparación con referencias humanas: TVSum, SumMe y la película"));
c.push(P("Esta sección responde a la pregunta del asesor: qué tanto se parece o se diferencia la selección de CAVA de la de un humano, con la misma vara en los tres conjuntos."));
c.push(H2("10.1 Lo que ya tenemos"));
c.push(table(["Conjunto", "Medida", "CAVA", "Uniforme", "Al azar", "Fuente"], [
  ["TVSum (50 videos)", "Recompensa z, highlights 10 %", "0,057", "0,322", "0,041", "EXP-031"],
  ["TVSum", "F1 al 15 %", "0,114", "—", "—", "EXP-031"],
  ["SumMe (25 videos)", "Recompensa z, highlights del producto", "0,158", "0,156", "0,002", "EXP-037 / 038"],
], [0.18, 0.3, 0.1, 0.12, 0.1, 0.2]));
c.push(P("En los dos conjuntos, la selección de CAVA no supera a la uniforme. Otani et al. (2019) mostraron que en TVSum resúmenes al azar obtienen un F1 cercano al estado del arte, así que estas referencias tienen poco poder para separar métodos."));
c.push(H2("10.2 Lo que falta: el punto de referencia humano"));
c.push(P("No hemos calculado **cuánto coincide un anotador con los demás**. Sin ese techo no se puede decir qué tan lejos está CAVA de una persona. Se propone una tabla única, con las mismas métricas para los tres conjuntos:"));
c.push(table(["Fila", "TVSum", "SumMe", "_Brand New Day_ (bloque B)"], [
  ["Humano contra el resto (dejando uno fuera)", "20 anotadores", "15–18 usuarios", "Participantes"],
  ["CAVA", "cava_runs_v1", "cava_runs_v1_summe", "Highlights 240 s"],
  ["Uniforme / U", "sí", "sí", "sí"],
  ["Centro", "sí", "sí", "sí"],
  ["Al azar (1 000 sorteos)", "sí", "sí", "sí"],
], [0.34, 0.2, 0.2, 0.26]));
c.push(P("**Métricas:** F1 al 15 % (media y máximo sobre anotadores), τ de Kendall y ρ de Spearman (Otani et al., 2019) y nuestra recompensa z. Para TVSum y SumMe es un cálculo en CPU sobre corridas que ya existen; se pre-registra como experimento propio antes de calcularlo."));

// 11
c.push(H1("11. Requisitos antes del evento"));
c.push(table(["#", "Tarea", "Estado", "Responsable"], [
  ["1", "Commit del pre-registro de EXP-040 (hoy sin confirmar en git)", "Pendiente", ""],
  ["2", "Firmar EXP-041 en docs/EXPERIMENT_LOG.md con este protocolo", "Pendiente", ""],
  ["3", "Generar U y S para la película: capítulos y highlights de 240 s (CPU, exp040_baselines.py con perfil film)", "Pendiente", ""],
  ["4", "Generar los highlights de 240 s de CAVA y verificar G-versión en los tres sistemas", "Pendiente", ""],
  ["5", "Quemar subtítulos en inglés en todas las versiones con el mismo procedimiento", "Pendiente", ""],
  ["6", "Cuadrícula de 97 miniaturas (una cada 90 s)", "Pendiente", ""],
  ["7", "Plataforma: visor de línea de tiempo, reproductor de pares, preguntas, telemetría, códigos y asignación por secuencia (sobre la página de etiquetado y la base de datos de EXP-040)", "Pendiente", ""],
  ["8", "Decidir el idioma de las etiquetas (inglés tal cual, o traducción automática igual para los tres)", "Pendiente", ""],
  ["9", "Demostración por storyline: congelar el paso storyline → secciones, o usar el mapa de tópicos", "Pendiente", ""],
  ["10", "Piloto con 3 personas y registro de los cambios", "Pendiente", ""],
  ["11", "Sala de cómputo, audífonos, archivos locales (sin depender del clúster); formulario del sorteo separado", "Pendiente", ""],
  ["12", "Tabla de techo humano de TVSum y SumMe (sección 10)", "Pendiente", ""],
], [0.05, 0.65, 0.13, 0.17]));

// 12
c.push(H1("12. Limitaciones"));
c.push(B("**Una película:** la inferencia es sobre personas, no sobre películas. EXP-040 cubre la generalización sobre videos."));
c.push(B("**Participantes que ya la vieron:** completan con su memoria lo que falta. Se mide representatividad, no comprensión de alguien nuevo."));
c.push(B("**Sesgo del recuerdo:** las personas recuerdan más las escenas de acción y el clímax. Es la referencia que buscamos, pero no equivale a una anotación exhaustiva."));
c.push(B("**Audio en inglés:** puede afectar la valoración; se mide con A7 y se analiza como moderador."));
c.push(B("**Tiempo limitado:** la línea de tiempo se juzga en 3 minutos; mide navegación y primera impresión, no uso prolongado."));
c.push(B("**Potencia:** con 60 personas, preferencias menores a ~67/33 pueden no detectarse."));
c.push(B("**Demostración no ciega:** los datos de E1 son descriptivos y no entran en los criterios."));

// Annex A
c.push(new Paragraph({ children: [new PageBreak()] }));
c.push(H1("Anexo A. Formato actual de segmentación y agregación de tópicos en CAVA"));
c.push(P("Estado del repositorio remoto (origin/main, Edgar100800/CAVA-TESIS): está 5 commits por delante de la copia local, pero solo con cambios de la tesis en LaTeX (portada, figuras y texto). El código de tópicos (topicagg/) no cambió, así que el formato descrito aquí es el mismo en las dos copias."));
c.push(H2("A.1 Flujo"));
c.push(N("**Unidades fijas:** el video se divide en unidades de 5 s (perfil film y documentary) o 10 s (meeting).", "flow"));
c.push(N("**Cuatro votantes independientes por unidad** (nunca se fusionan, ADR-0001): voz (log-mel + tono), visual (SigLIP del fotograma central), transcripción (Whisper large-v3 → embeddings bge) y VJudge (Qwen2.5-VL-7B resume bloques de ~40 s → bge).", "flow"));
c.push(N("**Gestor manage():** cada señal propone sus cortes con su propio percentil (p80 en film) y sus tópicos con retornos (p90). El consenso se forma por enlace promedio sobre la matriz de votos; una señal sin evidencia en una unidad se abstiene. El quorum es 2 en el nivel default y 4 en el nivel fine.", "flow"));
c.push(N("**Snap:** en film y documentary, cada frontera del mapa se ajusta a la frontera visual más cercana a 30 s o menos (EXP-027).", "flow"));
c.push(N("**Mapa de tópicos:** dos niveles (default y fine). Cada tópico tiene id, tramos (spans), duración, número de retornos, etiqueta (Qwen2.5-14B), procedencia por señal (acuerdo, soporte, coherencia) y banderas (no_topic, needs_review).", "flow"));
c.push(N("**Identidades:** nombres propios propagados por enlaces; voces por embedding WavLM-sv, Ward y K por BIC.", "flow"));
c.push(N("**Versiones:** capítulos, recap 60 s, highlights 10 %, hilos de tópico e hilos por hablante, con gate G-versión; clips mp4, playlists e índice.", "flow"));
c.push(H2("A.2 Valores en Brand New Day"));
c.push(table(["Nivel", "Tópicos", "Con retornos", "Duración mediana", "Máximo", "Tramos máx. por tópico"], [
  ["default", "104", "45", "37,5 s", "685 s", "19"],
  ["fine", "361", "25", "15 s", "190 s", "4"],
], [0.14, 0.14, 0.16, 0.2, 0.14, 0.22]));
c.push(table(["Versión del producto", "Clips", "Duración total"], [
  ["Capítulos completos", "103", "67,2 min"],
  ["Recap 60 s", "1", "1 min"],
  ["Highlights 10 %", "9", "14,5 min"],
  ["Hilos de tópico (3)", "19 / 15 / 15", "11,4 / 8,8 / 6,7 min"],
  ["Hilos por hablante (3)", "34 / 25 / 32", "14,5 min cada uno"],
], [0.4, 0.25, 0.35]));
c.push(P("La capa narrativa (ADR-0002: eventos, sinopsis global, tópicos narrativos gNNN y revisión de continuidad) es experimental, no ha corrido en GPU y no forma parte del sistema evaluado."));

// Annex B
c.push(H1("Anexo B. Películas de MovieNet con story beats y escenas"));
c.push(P("De las películas anotadas en MovieNet, **312** tienen a la vez **story** y **scene**:"));
c.push(B("**story:** párrafos de la sinopsis (entre 1 y 77 por película) con su **texto descriptivo**, el rango de shots, el rango en segundos y un puntaje de consistencia de la alineación (mínimo 0,80, mediana 0,96). Es la referencia de trama alineada al video."));
c.push(B("**scene:** fronteras de escena como rangos de shots. **No tienen descripción en texto**; solo el 31 % de las 40 472 escenas tiene etiqueta de lugar y el 22 % etiqueta de acción."));
c.push(B("MovieNet no distribuye los videos: hace falta una copia propia y alinear los tiempos de shot de MovieNet con esa copia antes de usar la referencia."));
c.push(B("**Splits:** val es el preferido (no se usó para entrenar); train se usó para ajustar parámetros del perfil (riesgo de fuga leve); test sigue bloqueado."));
c.push(P("Selección de películas conocidas por estudiantes (beats / escenas):"));
c.push(table(["Película", "IMDb", "Split", "Beats", "Escenas"], [
  ["Spider-Man (2002)", "tt0145487", "val", "10", "95"],
  ["Star Wars IV: A New Hope (1977)", "tt0076759", "val", "41", "128"],
  ["Star Wars V: The Empire Strikes Back (1980)", "tt0080684", "val", "24", "102"],
  ["Star Wars II: Attack of the Clones (2002)", "tt0121765", "val", "10", "114"],
  ["The Lord of the Rings: The Two Towers (2002)", "tt0167261", "val", "11", "145"],
  ["Indiana Jones and the Last Crusade (1989)", "tt0097576", "val", "11", "84"],
  ["V for Vendetta (2005)", "tt0434409", "val", "26", "329"],
  ["I, Robot (2004)", "tt0343818", "val", "12", "142"],
  ["Men in Black 3 (2012)", "tt1409024", "val", "8", "75"],
  ["The Bourne Identity (2002)", "tt0258463", "val", "6", "274"],
  ["The Sixth Sense (1999)", "tt0167404", "val", "5", "70"],
  ["The Avengers (2012)", "tt0848228", "train", "13", "138"],
  ["Avatar (2009)", "tt0499549", "train", "36", "108"],
  ["The Lord of the Rings: The Fellowship of the Ring (2001)", "tt0120737", "train", "5", "138"],
  ["The Lord of the Rings: The Return of the King (2003)", "tt0167260", "train", "16", "117"],
  ["Pirates of the Caribbean: Dead Man's Chest (2006)", "tt0383574", "train", "4", "72"],
  ["Star Trek (2009)", "tt0796366", "train", "27", "194"],
  ["The Matrix Reloaded (2003)", "tt0234215", "train", "48", "244"],
  ["The Social Network (2010)", "tt1285016", "train", "8", "195"],
  ["Finding Nemo (2003)", "tt0266543", "sin split", "20", "115"],
  ["Inception (2010)", "tt1375666", "test (bloqueado)", "29", "264"],
  ["Jurassic Park (1993)", "tt0107290", "test (bloqueado)", "11", "156"],
  ["Star Wars VII: The Force Awakens (2015)", "tt2488496", "test (bloqueado)", "23", "133"],
], [0.48, 0.15, 0.17, 0.1, 0.1]));
c.push(note("**Si se añade una segunda película con referencia de trama:** _Spider-Man_ (2002) es la más limpia (val, 10 beats con consistencia ≈0,98, mismo personaje). _The Avengers_ (2012) probablemente la vieron más estudiantes, pero está en train. Cualquiera de las dos requiere su copia, una corrida de CAVA en GPU y la alineación de tiempos, y entra con su propio pre-registro."));

// Annex C
c.push(H1("Anexo C. Glosario"));
c.push(table(["Término", "Significado"], [
  ["CAVA", "El sistema congelado: mapa de tópicos multimodal con retornos y sus versiones"],
  ["U", "Selección sin estructura: cortes o clips equiespaciados con el mismo presupuesto"],
  ["S", "Mejor señal sola: el mismo código de versiones sobre el mapa de la señal visual"],
  ["T / H", "Formatos evaluados: línea de tiempo por capítulos / highlights de 4 min"],
  ["Par de control", "Dos versiones idénticas; verifica atención"],
  ["Cobertura", "Fracción de los momentos esenciales de una persona que caen dentro de los clips de una versión"],
  ["Techo humano", "Qué tan bien las marcas de las demás personas cubren las de cada una con el mismo presupuesto"],
  ["G-versión", "Control automático de que cada versión respeta su presupuesto y formato"],
], [0.22, 0.78]));

// ---------------------------------------------------------------- document
const doc = new Document({
  creator: "CAVA",
  title: "EXP-041 · Evaluación con usuarios",
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", run: { font: FONT, size: 36, bold: true, color: "1A1A1A" }, paragraph: { spacing: { before: 0, after: 120 }, keepNext: true } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 28, bold: true, color: ACCENT }, paragraph: { spacing: { before: 320, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 23, bold: true, color: "262626" }, paragraph: { spacing: { before: 220, after: 100 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 21, bold: true }, paragraph: { spacing: { before: 160, after: 80 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 240 } } } },
      ] },
      ...["nums", "crit", "flow"].map((ref) => ({ reference: ref, levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 300 } } } },
      ] })),
    ],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: "CAVA · EXP-041 · página ", size: 16, color: "808080" }),
      new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "808080" }),
    ] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = process.argv[2];
  fs.writeFileSync(out, buf);
  console.log("wrote", out, buf.length);
});
