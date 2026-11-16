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

c.push(new Paragraph({ children: [new TextRun({ text: "CAVA · Evaluación con usuarios", font: FONT, size: 22, color: ACCENT, bold: true })], spacing: { after: 60 } }));
c.push(new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun("Proceso de la prueba A/B y criterios de evaluación")] }));
c.push(new Paragraph({ children: runs("Sesión con estudiantes UTEC sobre _Spider-Man: Brand New Day_ (2026)", { size: 24, color: "404040" }), spacing: { after: 200 } }));

// 1
c.push(H1("1. Propósito"));
c.push(P("Las referencias automáticas usadas hasta ahora (importancia humana de TVSum y SumMe, capítulos de autor) no distinguen a CAVA de selecciones simples y tienen sesgos propios, como la posición dentro del video. La medición que falta es la de personas."));
c.push(P("La sesión mide, con estudiantes que ya vieron la película, tres cosas:"));
c.push(N("si las **secciones** que CAVA elige representan la historia mejor que una selección sin estructura con el mismo presupuesto;"));
c.push(N("si la **búsqueda de escenas** basada en las descripciones de CAVA encuentra los momentos que las personas recuerdan mejor que una búsqueda que solo usa el diálogo;"));
c.push(N("cuáles son los **momentos esenciales** de la película según las personas, para construir una referencia humana comparable con TVSum y SumMe."));
c.push(note("**Alcance de lo que se podrá afirmar:** qué tan bien representan las versiones la historia para personas que ya la conocen. No se mide retención ni aprendizaje de alguien que no vio la película, y con una sola película la conclusión es sobre personas, no sobre películas."));

// 2
c.push(H1("2. Estado actual del sistema que se evalúa"));
c.push(table(["Componente", "Qué hace", "Estado"], [
  ["Mapa de tópicos y versiones", "Divide la película en unidades de 5 s; cuatro señales (voz, imagen, transcripción y resúmenes visuales) votan por separado y forman tópicos que pueden reaparecer. Produce capítulos, highlights y otros formatos.", "Completo para _Endgame_ y _Brand New Day_ (104 tópicos, 45 que reaparecen)."],
  ["Descripción por tópico (versión base)", "Qwen2.5-14B reescribe, para cada tópico de al menos 30 s, lo ya extraído (resúmenes visuales, diálogo, personajes) en cinco secciones: personajes, acciones, estados, ambiente y desarrollo. Las descripciones se indexan con BGE para buscar escenas por frase.", "Completa en la PC del laboratorio: _Endgame_ 59/59 y _Brand New Day_ 57/57 tópicos. La auditoría encontró respuestas cortadas (52 %), evidencia recortada, identidades dudosas, tópicos que juntan momentos separados e índice incompleto."],
  ["Descripción corregida (fase 1)", "Mismos tópicos y modelo; salida estructurada en inglés, cada afirmación ligada a su evidencia, sin recortes, con validación de respuestas cortadas o inválidas.", "En ejecución."],
  ["Escenas continuas (fase 2)", "Cortes que respetan imagen y voz, sin partir frases, con datos ya calculados.", "Ejecutada, sin validar: falta la anotación manual de cortes."],
  ["Fases 3 a 5", "Personajes con evidencia, revisión visual en casos dudosos, búsqueda por intervalo real.", "Definidas, no implementadas."],
], [0.2, 0.45, 0.35]));
c.push(P("**Regla de congelamiento.** Antes del piloto se fija qué versión de cada componente entra en la sesión, y no cambia hasta terminar. Para la búsqueda: si la fase 1 termina y pasa su validación, se usa la descripción corregida; si no, la versión base, y se declara. Las fases 2 a 5 que no estén validadas a esa fecha no entran en las comparaciones; pueden mostrarse solo en la demostración final."));

// 3
c.push(H1("3. Comparación directa con TVSum y SumMe frente a la referencia humana"));
c.push(H2("3.1 Lo que ya tenemos"));
c.push(table(["Conjunto", "Medida", "CAVA", "Uniforme", "Al azar"], [
  ["TVSum (50 videos, 20 anotadores)", "Recompensa z, highlights 10 %", "0,057", "0,322", "0,041"],
  ["TVSum", "F1 al 15 %", "0,114", "—", "—"],
  ["SumMe (25 videos, 15–18 usuarios)", "Recompensa z, highlights del producto", "0,158", "0,156", "0,002"],
], [0.3, 0.32, 0.12, 0.14, 0.12]));
c.push(P("En los dos conjuntos la selección de CAVA no supera a una selección uniforme. Otani et al. (2019) mostraron que en TVSum los resúmenes al azar obtienen un F1 cercano al estado del arte: estas referencias separan poco a los métodos."));
c.push(H2("3.2 Lo que falta: cuánto coincide un humano con los demás"));
c.push(P("No se ha medido el **techo humano**: qué tan bien coincide cada anotador con el resto. Sin ese punto no se puede decir qué tan lejos está CAVA de una persona. Se calculará una tabla única, con las mismas métricas en los tres conjuntos:"));
c.push(table(["Fila", "TVSum", "SumMe", "_Brand New Day_"], [
  ["Humano frente al resto (dejando uno fuera)", "20 anotadores", "15–18 usuarios", "Participantes de la sesión (bloque B)"],
  ["CAVA", "sí", "sí", "Highlights de 4 min"],
  ["Selección uniforme", "sí", "sí", "sí"],
  ["Al azar (1 000 sorteos)", "sí", "sí", "sí"],
], [0.34, 0.18, 0.18, 0.3]));
c.push(P("**Métricas:** F1 al 15 % (media y máximo sobre anotadores), τ de Kendall y ρ de Spearman (Otani et al., 2019) y la recompensa z por segundo que ya usamos. Para TVSum y SumMe el cálculo usa corridas que ya existen; para la película, la referencia sale de los momentos que marcan los participantes."));

// 4
c.push(H1("4. Diseño de la sesión"));
c.push(H2("4.1 Participantes"));
c.push(B("Estudiantes UTEC de 18 años o más que vieron _Spider-Man: Brand New Day_. Convocatoria por Freshit; cinco vales de consumo sorteados entre quienes completen la sesión, sin relación con sus respuestas."));
c.push(B("**Meta:** 60 participantes en dos sesiones de unos 30. **Mínimo:** 40."));
c.push(B("Cada persona se identifica con un código. Nombre y correo para el sorteo van en un formulario aparte que no se cruza con las respuestas."));
c.push(B("La convocatoria habla de «resúmenes automáticos de películas» y no de «nuestro modelo», para no inducir preferencias. CAVA se presenta abiertamente solo al final."));
c.push(H2("4.2 Material"));
c.push(B("Película de 145 min con audio en inglés y subtítulos en inglés quemados, idénticos en todas las versiones (el archivo no tiene audio en español)."));
c.push(B("**Sistemas en las comparaciones:** CAVA y **U**, una selección sin estructura (cortes o clips equiespaciados) con el mismo presupuesto, el mismo corte y codificación y el mismo modelo de etiquetas. Solo cambia qué tramos se eligen."));
c.push(B("**Formatos:** línea de tiempo por capítulos (barra con bloques, etiqueta y miniatura; un clic reproduce el clip) y highlights de 4 minutos (240 s para ambos sistemas)."));
c.push(B("**Búsqueda:** índice de descripciones de CAVA frente a un índice que solo usa el diálogo transcrito de los mismos tramos, con el mismo modelo de búsqueda y los 3 primeros resultados."));
c.push(B("Cuadrícula neutral de 97 miniaturas (una cada 90 s) para que las personas ubiquen sus momentos sin que ningún sistema influya."));
c.push(H2("4.3 Agenda (90 minutos, sala de cómputo con audífonos)"));
c.push(table(["Min", "Bloque", "Actividad"], [
  ["0–10", "A · Registro", "Consentimiento, código y preguntas de filtro"],
  ["10–25", "B · Recuerdo", "Sin ver ningún clip: sinopsis propia y 5–8 momentos esenciales ubicados en la cuadrícula"],
  ["25–47", "C · Comparaciones A/B", "Tres pares a ciegas: línea de tiempo, highlights y un par de control"],
  ["47–59", "D · Búsqueda A/B", "Tres de sus propios momentos como búsqueda; dos listas de resultados a ciegas"],
  ["59–67", "E · Cierre", "Preferencias de formato y comentarios"],
  ["67–70", "—", "Se bloquean las respuestas"],
  ["70–90", "F · Demostración y grupo focal", "CAVA se presenta abiertamente; conversación guiada; sorteo"],
], [0.1, 0.27, 0.63]));
c.push(P("El orden importa: el recuerdo va antes de ver cualquier clip para que la referencia humana no se contamine, y la demostración va al final para no condicionar los juicios. El lado (A o B) de cada sistema y el orden de los formatos se alternan entre participantes. Antes de la primera sesión se hace un piloto con 3 personas ajenas al equipo."));

// 5
c.push(H1("5. Qué se mide"));
c.push(table(["#", "Medida", "Cómo se obtiene", "Tipo"], [
  ["M1", "Preferencia por la línea de tiempo de CAVA frente a U", "Elección a ciegas en el par de línea de tiempo", "Principal"],
  ["M2", "Preferencia por los highlights de CAVA frente a U", "Elección a ciegas en el par de highlights", "Principal"],
  ["M3", "Recall@3 de la búsqueda: si el momento que la persona marcó aparece entre los 3 primeros resultados", "Momentos del bloque B usados como búsquedas, comparados con su minuto marcado; descripciones frente a solo diálogo", "Principal"],
  ["M4", "Cobertura de momentos esenciales", "Fracción de los momentos marcados por cada persona que caen dentro de los highlights de cada sistema", "Secundaria"],
  ["M5", "Valoraciones de cada versión", "Escalas de 1 a 5 (sección 6, C3)", "Secundaria"],
  ["M6", "Preferencia declarada en la búsqueda", "Elección a ciegas entre las dos listas (D1)", "Secundaria"],
  ["M7", "Formato preferido, utilidad y opiniones", "Bloques E y F", "Cualitativa"],
], [0.06, 0.32, 0.44, 0.18]));

// 6
c.push(H1("6. Preguntas a los participantes"));
c.push(P("Las escalas de acuerdo van de 1 (totalmente en desacuerdo) a 5 (totalmente de acuerdo)."));
c.push(H2("Bloque A · Registro y filtro"));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["A1", "Carrera y ciclo", "Lista"],
  ["A2", "Rango de edad", "18–20 · 21–23 · 24–26 · 27 o más"],
  ["A3", "¿Viste _Spider-Man: Brand New Day_?", "No · Sí, una vez · Sí, más de una vez"],
  ["A4", "¿Cuándo la viste por última vez?", "Menos de 1 mes · 1 a 3 meses · más de 3 meses"],
  ["A5", "¿En qué idioma la viste?", "Doblada · En inglés con subtítulos · En inglés sin subtítulos"],
  ["A6", "¿Qué tanto entiendes el inglés hablado en una película?", "1 (casi nada) a 5 (todo)"],
  ["A7", "¿Qué tanto recuerdas la historia?", "1 (muy poco) a 5 (casi todo)"],
  ["A8", "¿Con qué frecuencia ves resúmenes o explicaciones de películas (YouTube, TikTok)?", "Nunca · A veces · Frecuentemente"],
], [0.07, 0.58, 0.35]));
c.push(H2("Bloque B · Recuerdo (antes de ver cualquier clip)"));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["B1", "En una o dos frases, ¿de qué trata la película?", "Texto"],
  ["B2", "Escribe, en orden, entre 5 y 8 momentos que no pueden faltar en un resumen de la película.", "Lista de textos"],
  ["B3", "Marca en la cuadrícula la imagen donde ocurre cada uno de esos momentos. Si no lo ubicas, déjalo sin marcar.", "Hasta 8 miniaturas"],
], [0.07, 0.63, 0.3]));
c.push(H2("Bloque C · Comparaciones A/B a ciegas"));
c.push(P("Cada par muestra dos versiones del mismo formato, A y B, sin indicar qué sistema produjo cada una. Hay que abrir las dos antes de responder. Tiempo por versión: 3 min en la línea de tiempo y 4 min en los highlights. El par de control muestra dos versiones idénticas."));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["C1", "¿Cuál de las dos versiones representa mejor la película?", "A · B · Iguales"],
  ["C2", "¿Qué tan seguro estás de tu elección?", "Poco · Algo · Muy seguro"],
  ["C3a", "Incluye los momentos que considero esenciales.", "1–5, para A y para B"],
  ["C3b", "Se entiende la secuencia de la historia, sin saltos que confundan.", "1–5, para A y para B"],
  ["C3c", "No incluye partes irrelevantes (créditos, logos, relleno).", "1–5, para A y para B"],
  ["C3d", "Los títulos describen bien lo que pasa en cada sección (solo línea de tiempo).", "1–5, para A y para B"],
  ["C3e", "Se lo mostraría a alguien que no vio la película para que entienda de qué trata.", "1–5, para A y para B"],
  ["C4", "¿Qué momento esencial faltó? ¿Qué parte sobraba? (opcional)", "Texto"],
], [0.07, 0.63, 0.3]));
c.push(H2("Bloque D · Búsqueda de escenas A/B a ciegas"));
c.push(P("La plataforma toma tres de los momentos que la persona escribió en B2 y marcó en B3. Cada uno se usa como búsqueda en los dos índices (las búsquedas se traducen al inglés con el mismo procedimiento para ambos). Se muestran lado a lado los 3 primeros resultados de cada índice, como clips, sin texto que delate el sistema."));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["D1", "¿En qué lista aparece el momento que buscabas?", "A · B · En ambas · En ninguna"],
  ["D2", "Si aparece, ¿en qué posición?", "1.º · 2.º · 3.º (para cada lista)"],
  ["D3", "¿Qué lista te sería más útil para encontrar ese momento?", "A · B · Iguales"],
], [0.07, 0.63, 0.3]));
c.push(H2("Bloque E · Cierre"));
c.push(table(["#", "Pregunta", "Respuesta"], [
  ["E1", "Si tuvieras que recordar una película antes de ver su secuela, ¿qué usarías?", "Línea de tiempo con capítulos · Video de highlights · Búsqueda de escenas · Un video resumen de YouTube · Volvería a ver la película"],
  ["E2", "¿En qué situación usarías una línea de tiempo con capítulos o una búsqueda de escenas?", "Texto"],
  ["E3", "¿Qué les falta a estas versiones para que te sean útiles?", "Texto"],
  ["E4", "En general, ¿qué tan útil te parece un sistema que resuma películas de esta manera?", "1 (nada útil) a 5 (muy útil)"],
], [0.07, 0.5, 0.43]));
c.push(H2("Bloque F · Demostración y grupo focal"));
c.push(P("Con las respuestas ya bloqueadas, se presenta CAVA: el storyline de la película con las secciones que el sistema asocia a cada momento, y la búsqueda en vivo. Guía de conversación:"));
c.push(B("¿Qué les sorprendió de las secciones que eligió el sistema?"));
c.push(B("¿Qué momentos esperaban ver y no aparecieron?"));
c.push(B("¿Confiarían en este tipo de resumen para decidir si ver una película o para recordarla antes de una secuela? ¿Por qué?"));
c.push(B("¿Qué cambiarían de la forma de presentarlo: línea de tiempo, video o búsqueda?"));

// 7
c.push(H1("7. Información que se recopila"));
c.push(table(["Dato", "Origen", "Para qué se usa"], [
  ["Respuestas de filtro (A1–A8)", "Bloque A", "Elegibilidad; analizar el efecto de la familiaridad con la película y del inglés"],
  ["Sinopsis y momentos esenciales en texto (B1, B2)", "Bloque B", "Búsquedas para M3; análisis cualitativo"],
  ["Minuto de cada momento marcado (B3)", "Bloque B", "Referencia humana de la película (sección 3), cobertura (M4) y acierto de la búsqueda (M3)"],
  ["Elección, seguridad, escalas y comentarios por par (C1–C4)", "Bloque C", "M1, M2 y M5"],
  ["Respuestas de búsqueda (D1–D3) y resultados mostrados", "Bloque D", "M3 y M6"],
  ["Lado y orden en que se mostró cada sistema", "Plataforma", "Verificar el contrabalanceo"],
  ["Tiempo por versión, reproducciones, saltos y tiempo hasta decidir", "Plataforma", "Exclusiones y esfuerzo por versión"],
  ["Preferencias y opiniones (E1–E4)", "Bloque E", "M7"],
  ["Notas del grupo focal", "Moderador", "M7"],
], [0.38, 0.17, 0.45]));
c.push(P("No se guarda ningún dato que identifique a la persona junto a sus respuestas."));

// 8
c.push(H1("8. Cómo se evalúa"));
c.push(H2("8.1 Criterios principales (fijados antes de la sesión)"));
c.push(table(["Medida", "Prueba", "Se cumple si"], [
  ["M1 · Línea de tiempo", "Proporción de personas que prefieren CAVA, sin empates; prueba binomial exacta, IC 95 %", "La proporción es mayor a 0,50 y el IC no incluye 0,50"],
  ["M2 · Highlights", "Igual que M1", "Igual que M1"],
  ["M3 · Búsqueda", "Diferencia de Recall@3 (descripciones menos solo diálogo), pareada por búsqueda, IC 95 % por bootstrap agrupando por persona; también frente a resultados al azar", "La diferencia es positiva y su IC no incluye 0"],
], [0.2, 0.5, 0.3]));
c.push(P("Las tres medidas principales se corrigen juntas por comparaciones múltiples (Holm). Un acierto en M3 cuenta cuando algún resultado se cruza con el intervalo de 90 s que la persona marcó."));
c.push(H2("8.2 Tamaño de muestra"));
c.push(P("En M1 y M2 todas las personas juzgan el mismo par, así que cada una aporta un juicio independiente por formato. Preferencia mínima detectable (α 0,05, potencia 0,8, sin empates):"));
c.push(table(["Juicios sin empate", "Preferencia mínima detectable"], [
  ["47", "70 / 30"],
  ["62", "67,5 / 32,5"],
  ["85", "65 / 35"],
], [0.5, 0.5]));
c.push(P("Con 60 participantes, una preferencia menor a ~67/33 puede no detectarse; se declara de antemano. M3 tiene más poder: cada persona aporta entre 5 y 8 momentos marcados (300 a 480 búsquedas en total) para el cálculo objetivo."));
c.push(H2("8.3 Exclusiones"));
c.push(B("Quien elige A o B en el par de control (versiones idénticas): se excluyen sus juicios del bloque C."));
c.push(B("Un par en el que alguna versión se vio menos de 30 s: se excluye ese par."));
c.push(B("Menos de 3 momentos marcados en B3: se excluye de M3 y M4."));
c.push(B("Quien no vio la película no participa en los bloques B a E."));
c.push(H2("8.4 Lectura de resultados"));
c.push(B("**CAVA gana en línea de tiempo y highlights:** la estructura multimodal mejora la representación de la historia en ambos formatos."));
c.push(B("**Gana solo en línea de tiempo:** la estructura ayuda a navegar, pero no a elegir los mejores momentos, como ya se vio en TVSum y SumMe."));
c.push(B("**Sin diferencia detectable:** se reporta el efecto mínimo que el tamaño de muestra podía detectar."));
c.push(B("**La búsqueda con descripciones supera a la de solo diálogo:** la información visual aporta para encontrar momentos, en especial en escenas con poco diálogo (se desglosa por tipo de momento)."));
c.push(B("**Expectativa declarada:** CAVA gana en línea de tiempo; resultado incierto en highlights; la búsqueda con descripciones supera a la de solo diálogo."));

// 9
c.push(H1("9. Limitaciones"));
c.push(B("Una sola película: la conclusión es sobre personas, no sobre películas. La evaluación paralela con videos de YouTube cubre la variedad de contenido."));
c.push(B("Los participantes ya conocen la historia y completan con su memoria lo que falta en un resumen."));
c.push(B("Las personas recuerdan más la acción y el clímax: es la referencia buscada, pero no es una anotación exhaustiva."));
c.push(B("Audio y descripciones en inglés; la búsqueda depende de traducir las consultas. Se mide la comprensión del inglés para analizar su efecto."));
c.push(B("La línea de tiempo se juzga en 3 minutos: mide navegación y primera impresión, no uso prolongado."));
c.push(B("La descripción por tópico aún tiene problemas de calidad documentados; se evalúa la versión congelada, sea la base o la corregida, y se declara cuál."));
c.push(B("La demostración no es ciega: sus resultados son solo cualitativos."));
// ---------------------------------------------------------------- document
const doc = new Document({
  creator: "CAVA",
  title: "CAVA · Evaluación con usuarios: proceso A/B y criterios",
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
      new TextRun({ text: "CAVA · Evaluación con usuarios · página ", size: 16, color: "808080" }),
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
