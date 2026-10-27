/* Chloe Creaciones · POS — utilidades compartidas */

const App = (function () {
  // Ruta de los archivos estáticos (la define la plantilla); todo se sirve localmente, sin internet
  const STATIC = window.APP_STATIC || '/static/';
  const moneyFmt = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });
  const numFmt = new Intl.NumberFormat('es-CL');

  // Acepta números o textos; las plantillas escriben los decimales con coma ("5379,31"), sin separador de miles
  function money(v) { return moneyFmt.format(Math.round(Number(typeof v === 'string' ? v.replace(',', '.') : v) || 0)); }
  function num(v) { return numFmt.format(Number(v) || 0); }

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  const toastIcons = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };

  function toast(message, type = 'info', ms = 3200) {
    let stack = document.querySelector('.toast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'toast-stack';
      document.body.appendChild(stack);
    }
    const el = document.createElement('div');
    el.className = `app-toast ${type}`;
    el.setAttribute('role', 'status');
    el.innerHTML = `<i class="bi ${toastIcons[type] || toastIcons.info}"></i><div>${esc(message)}</div>`;
    stack.appendChild(el);
    setTimeout(() => {
      el.style.transition = 'opacity .2s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 200);
    }, ms);
  }

  function formatDateTime(d) {
    return new Date(d).toLocaleString('es-CL', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  /* ---------- Datos de cada negocio que salen en la boleta (edítalos aquí) ----------
     La venta indica de qué negocio es con venta.negocio ('uniformes' si no lo dice) */
  const NEGOCIOS = {
    uniformes: {
      nombre: 'Chloe Creaciones',
      bajada: 'Uniformes escolares',
      lineas: [
        // 'RUT: 12.345.678-9',
        // 'Av. Siempre Viva 123, Santiago',
        // 'Tel: +56 9 1234 5678',
      ],
      pie: '¡Gracias por su compra!',
    },
    libreria: {
      nombre: 'Chloe Librería',
      bajada: 'Librería y útiles escolares',
      lineas: [],
      pie: '¡Gracias por su compra!',
    },
    arriendos: {
      nombre: 'Chloe Arriendos',
      bajada: 'Arriendo de trajes folclóricos',
      lineas: [],
      pie: 'Cuide los trajes y devuélvalos en la fecha indicada. ¡Gracias!',
    },
  };

  /* Rollo de la impresora de boletas (se elige en Sistema → Impresora de boletas).
     util = ancho de la boleta, en mm: lo que la impresora alcanza a imprimir (48 / 72 mm) menos 2 mm por lado,
     para que nada quede cortado en el borde */
  const ROLLOS = { 58: { util: 44, letra: 12 }, 80: { util: 68, letra: 13 } };
  const ANCHO_ROLLO = ROLLOS[window.APP_BOLETA_ANCHO] ? window.APP_BOLETA_ANCHO : 58;
  const ROLLO = ROLLOS[ANCHO_ROLLO];

  /* Formas de pago (las mismas claves que Venta.METODOS_PAGO en models.py) */
  const METODOS_PAGO = {
    efectivo:      { nombre: 'Efectivo',      icono: 'bi-cash-coin' },
    debito:        { nombre: 'Débito',        icono: 'bi-credit-card' },
    credito:       { nombre: 'Crédito',       icono: 'bi-credit-card-2-front' },
    transferencia: { nombre: 'Transferencia', icono: 'bi-bank' },
  };

  /* Carga un script externo una sola vez */
  const scriptsCargados = {};
  function loadScript(src) {
    if (!scriptsCargados[src]) {
      scriptsCargados[src] = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = () => { delete scriptsCargados[src]; reject(new Error('No se pudo cargar ' + src)); };
        document.head.appendChild(s);
      });
    }
    return scriptsCargados[src];
  }

  /* ---------- Conjuntos (copia de AppInventario/conjuntos.py: mantener ambas iguales) ----------
     lineas: [{id, uniforme_id, talla_id, colegio_id, precio, cantidad}]; conjuntos: los de /api/conjuntos/
     Devuelve { sets: [{conjunto_id, nombre, precio, piezas: [linea_id], tallas: [talla_id]}], cobrado: {linea_id: monto} } */
  function armarConjuntos(lineas, conjuntos) {
    const unidades = [];
    lineas.forEach(l => { for (let i = 0; i < l.cantidad; i++) unidades.push({ ...l, usada: false }); });
    const sets = [];
    for (const c of conjuntos) {
      for (;;) {
        const armado = buscarSet(unidades, c);
        if (!armado) break;
        const normal = armado.piezas.reduce((a, u) => a + Number(u.precio), 0);
        if (armado.precio >= normal) break;
        armado.piezas.forEach(u => { u.usada = true; });
        sets.push({ conjunto_id: c.id, nombre: c.nombre, precio: armado.precio,
                    piezas: armado.piezas.map(u => u.id), tallas: armado.piezas.map(u => u.talla_id), _u: armado.piezas });
      }
    }
    const cobrado = Object.fromEntries(lineas.map(l => [l.id, 0]));
    unidades.forEach(u => { if (!u.usada) cobrado[u.id] += Number(u.precio); });
    sets.forEach(s => {
      const normal = s._u.reduce((a, u) => a + Number(u.precio), 0) || 1;
      let repartido = 0;
      s._u.forEach((u, i) => {
        const parte = i === s._u.length - 1 ? s.precio - repartido : Math.round(s.precio * Number(u.precio) / normal);
        repartido += parte;
        cobrado[u.id] += parte;
      });
      delete s._u;
    });
    return { sets, cobrado };
  }

  function buscarSet(unidades, c) {
    const libres = unidades.filter(u => !u.usada);
    const primeras = libres.filter(u => u.uniforme_id === c.componentes[0] && (c.colegio_id === null || u.colegio_id === c.colegio_id));
    for (const primera of primeras) {
      let piezas = [primera];
      for (const comp of c.componentes.slice(1)) {
        const candidatas = libres.filter(u => u.uniforme_id === comp && u.colegio_id === primera.colegio_id && !piezas.includes(u));
        if (!candidatas.length) { piezas = null; break; }
        const misma = candidatas.filter(u => u.talla_id === primera.talla_id);
        piezas.push((misma.length ? misma : candidatas)[0]);
      }
      if (piezas) {
        const precios = piezas.map(u => c.precios_talla[String(u.talla_id)] ?? c.precio);
        return { piezas, precio: Math.max(...precios) };
      }
    }
    return null;
  }

  /* Líneas para mostrar al cliente (boleta / pantalla del cliente): cada conjunto es un ítem con su
     precio y sus piezas; el resto de los productos, con su precio normal. Nunca se muestra "descuento". */
  function lineasBoleta(venta) {
    const usadas = {};
    (venta.conjuntos || []).forEach(c => c.piezas.forEach(p => { usadas[p.inventario_id] = (usadas[p.inventario_id] || 0) + 1; }));
    const conjuntos = (venta.conjuntos || []).map(c => ({
      tipo: 'conjunto', nombre: c.nombre, talla: c.talla, cantidad: 1, precio: c.precio, subtotal: c.precio,
      detalle: c.piezas.map(p => p.nombre).join(' + '),
    }));
    // Conjuntos iguales (mismo nombre, talla y piezas) se agrupan: "2 x $10.000"
    const agrupados = [];
    conjuntos.forEach(c => {
      const igual = agrupados.find(a => a.nombre === c.nombre && a.talla === c.talla && a.detalle === c.detalle && a.precio === c.precio);
      if (igual) { igual.cantidad++; igual.subtotal += c.precio; } else agrupados.push(c);
    });
    const sueltos = venta.items.map(i => {
      const cant = i.cantidad - (usadas[i.inventario_id] || 0);
      return cant > 0 ? { tipo: 'item', nombre: i.nombre, talla: i.talla, colegio: i.colegio, cantidad: cant, precio: i.precio, subtotal: cant * i.precio } : null;
    }).filter(Boolean);
    return agrupados.concat(sueltos);
  }

  /* ---------- Boleta ----------
     venta = { id, fecha, total, items: [{inventario_id, nombre, talla, colegio, cantidad, precio, subtotal}],
               conjuntos?: [...], recibido?, vuelto? } */
  function receiptHtml(venta) {
    const NEGOCIO = NEGOCIOS[venta.negocio] || NEGOCIOS.uniformes;
    // Uniformes: «Polerón · T. 10» y el colegio debajo. Librería: el producto y su marca debajo (sin talla)
    const rows = lineasBoleta(venta).map(i => {
      const detalle = i.tipo === 'conjunto' ? i.detalle : i.colegio;
      return `
      <tr><td colspan="2"><strong>${esc(i.nombre)}${i.talla ? ' · T. ' + esc(i.talla) : ''}</strong></td></tr>
      <tr><td style="padding-left:2ch">${i.cantidad} x ${money(i.precio)}${detalle ? `<br><small>${esc(detalle)}</small>` : ''}</td><td class="r">${money(i.subtotal)}</td></tr>`;
    }).join('');
    // La forma de pago no se imprime en la boleta; solo el vuelto cuando se pagó en efectivo
    const pago = venta.recibido ? `
      <tr><td>Recibido</td><td class="r">${money(venta.recibido)}</td></tr>
      <tr><td>Vuelto</td><td class="r">${money(venta.vuelto)}</td></tr>` : '';
    const unidades = venta.items.reduce((a, i) => a + i.cantidad, 0);
    return `
      <div class="receipt" style="width:${ROLLO.util}mm;font-size:${ROLLO.letra}px">
        <h3>${esc(NEGOCIO.nombre)}</h3>
        <div class="center">${esc(NEGOCIO.bajada)}</div>
        ${NEGOCIO.lineas.map(l => `<div class="center">${esc(l)}</div>`).join('')}
        <hr>
        <div><strong>${esc(venta.titulo || "Boleta")} N° ${esc(venta.folio ?? venta.id ?? "—")}</strong></div>
        <div>${esc(formatDateTime(venta.fecha))}</div>
        ${venta.anulada ? `<div class="center total" style="margin-top:6px">*** VENTA ANULADA ***</div>
        <div class="center">${esc(formatDateTime(venta.fecha_anulacion))}${venta.motivo_anulacion ? ' · ' + esc(venta.motivo_anulacion) : ''}</div>` : ''}
        <hr>
        <table>${rows}</table>
        <hr>
        <table>
          <tr><td>Unidades</td><td class="r">${unidades}</td></tr>
          <tr class="total"><td>TOTAL</td><td class="r">${money(venta.total)}</td></tr>
          ${pago}
          ${(venta.extras || []).map(x => `<tr${x.destacar ? ' class="total"' : ''}><td>${esc(x.t)}</td><td class="r">${esc(x.v)}</td></tr>`).join('')}
        </table>
        ${(venta.leyenda || []).map(l => `<div class="center" style="margin-top:4px">${esc(l)}</div>`).join('')}
        <hr>
        <div class="center">${esc(NEGOCIO.pie)}</div>
      </div>`;
  }

  /* ---------- Impresora de boletas ----------
     Antes de imprimir se revisa que Windows tenga una impresora de boletas; si no, se avisa y se ofrece
     instalar el driver. La revisión tarda unos segundos, así que se recuerda por 10 minutos. */
  const IMP = window.APP_IMPRESORA || null;
  const IMP_CACHE = 'chloe-impresora';
  let impPendiente = null;

  function estadoImpresora(forzar = false) {
    if (!IMP) return Promise.resolve(null);
    if (!forzar) {
      try {
        const c = JSON.parse(sessionStorage.getItem(IMP_CACHE));
        if (c && Date.now() - c.t < 10 * 60 * 1000) return Promise.resolve(c.estado);
      } catch (e) { /* sin caché */ }
      if (impPendiente) return impPendiente;
    }
    impPendiente = fetch(IMP.estado).then(r => r.ok ? r.json() : null).then(estado => {
      try { if (estado) sessionStorage.setItem(IMP_CACHE, JSON.stringify({ t: Date.now(), estado })); } catch (e) { /* sin caché */ }
      return estado;
    }).catch(() => null).finally(() => { impPendiente = null; });
    return impPendiente;
  }

  function instalarDriver(ancho) {
    return fetch(IMP.instalar, { method: 'POST', headers: { 'X-CSRFToken': IMP.csrf, 'Content-Type': 'application/json' }, body: JSON.stringify({ ancho }) })
      .then(r => r.json().then(d => { if (!r.ok) throw new Error(d.message || 'No se pudo abrir el instalador'); }));
  }

  /* Impresoras térmicas instaladas que sirven para el ancho de rollo pedido (las de ancho desconocido sirven para todo) */
  function termicasPara(estado, ancho) {
    return estado.boletas.filter(i => !ancho || !i.ancho || i.ancho === ancho);
  }

  /* Ventana de aviso cuando no está la impresora térmica que se necesita. Resuelve true = imprimir igual, false = cancelar */
  function avisoSinImpresora(estado, { ancho, uso }) {
    const titulo = `Impresora de ${uso} (rollo de ${ancho} mm)`;
    return new Promise(resolve => {
      const el = document.createElement('div');
      el.className = 'modal fade';
      el.tabIndex = -1;
      el.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header"><h5 class="modal-title"><i class="bi bi-printer me-2"></i>${esc(titulo)}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button></div>
            <div class="modal-body"></div>
            <div class="modal-footer">
              <button type="button" class="btn btn-light-border me-auto" data-acc="igual">Imprimir de todas formas</button>
              <button type="button" class="btn btn-light-border" data-acc="revisar"><i class="bi bi-arrow-clockwise me-1"></i>Volver a revisar</button>
              <button type="button" class="btn btn-primary" data-acc="instalar"><i class="bi bi-download me-1"></i>Instalar driver de ${ancho} mm</button>
            </div>
          </div>
        </div>`;
      document.body.appendChild(el);
      const cuerpo = el.querySelector('.modal-body');
      const btnInstalar = el.querySelector('[data-acc="instalar"]');
      const pintar = (e, nota = '') => {
        cuerpo.innerHTML = (e.sin_driver
          ? `<p class="mb-2"><strong>Hay una impresora térmica conectada, pero le falta su driver.</strong></p>`
          : `<p class="mb-2"><strong>No se encontró la impresora de ${esc(uso)} de ${ancho} mm.</strong> Revisa que esté encendida y conectada por USB.</p>`)
          + (e.driver_disponible
            ? '<p class="mb-0 small text-secondary">«Instalar driver» abre el instalador del fabricante: Windows pedirá permiso; acepta y sigue los pasos. Al terminar, presiona «Volver a revisar».</p>'
            : '<p class="mb-0 small text-secondary">El driver se instala desde el programa instalado en el POS (Sistema → Impresoras térmicas).</p>')
          + nota;
        btnInstalar.classList.toggle('d-none', !e.driver_disponible);
      };
      pintar(estado);
      let resultado = false;
      const modal = new bootstrap.Modal(el);
      el.addEventListener('click', async ev => {
        const btn = ev.target.closest('[data-acc]');
        if (!btn) return;
        const acc = btn.dataset.acc;
        if (acc === 'igual') { resultado = true; modal.hide(); return; }
        btn.disabled = true;
        if (acc === 'instalar') {
          try {
            await instalarDriver(ancho);
            pintar(estado, '<div class="alert alert-info small mt-3 mb-0">Se abrió el instalador. Cuando termine, presiona «Volver a revisar».</div>');
          } catch (err) { toast(err.message, 'error', 6000); }
        } else {
          const nuevo = await estadoImpresora(true);
          const lista = nuevo ? termicasPara(nuevo, ancho) : [];
          if (lista.length) {
            toast(`Impresora lista: ${lista[0].nombre}. Elígela en la ventana de impresión.`, 'success', 6000);
            resultado = true; modal.hide(); return;
          }
          if (nuevo) estado = nuevo;
          pintar(estado, `<div class="alert alert-warning small mt-3 mb-0">Todavía no aparece la impresora de ${esc(uso)}.</div>`);
        }
        btn.disabled = false;
      });
      el.addEventListener('hidden.bs.modal', () => { el.remove(); resolve(resultado); });
      modal.show();
    });
  }

  /* Antes de imprimir: revisa que esté instalada la impresora térmica del ancho pedido; si no, avisa.
     Resuelve true = seguir imprimiendo, false = cancelar */
  async function verificarImpresora({ ancho, uso }) {
    const estado = await estadoImpresora();
    if (!estado || termicasPara(estado, ancho).length) return true;
    return avisoSinImpresora(estado, { ancho, uso });
  }

  /* Nombre de la impresora térmica para ese ancho de rollo (para recordar cuál elegir en la ventana de impresión) */
  async function nombreImpresora(ancho = ANCHO_ROLLO) {
    const estado = await estadoImpresora();
    if (!estado) return null;
    const exacta = estado.boletas.find(i => i.ancho === ancho);
    return (exacta || termicasPara(estado, ancho)[0] || {}).nombre || null;
  }

  async function printReceipt(venta) {
    if (!(await verificarImpresora({ ancho: ANCHO_ROLLO, uso: 'boletas' }))) return;
    imprimirBoleta(venta);
  }

  function imprimirBoleta(venta) {
    // Sin tamaño de hoja: se usa el papel del driver (rollo de 48 mm imprimibles x 1 m), con la boleta
    // arriba y sin márgenes. Si se pide un tamaño que el driver no tiene, el navegador achica la
    // boleta y la centra en ese metro de papel.
    let st = document.getElementById('receipt-page-css');
    if (!st) { st = document.createElement('style'); st.id = 'receipt-page-css'; document.head.appendChild(st); }
    st.textContent = '@media print { @page { margin: 0; } #print-area { padding: 2mm 0; } }';
    document.getElementById('print-area').innerHTML = receiptHtml(venta);
    window.print();
  }

  /* Descarga la boleta como PDF en formato de rollo (58 u 80 mm, según la impresora) */
  async function downloadReceipt(venta) {
    try {
      await loadScript(STATIC + 'vendor/html2pdf/html2pdf.bundle.min.js');
    } catch (e) {
      toast('No se pudo preparar el PDF (¿hay conexión a internet?)', 'error');
      return;
    }
    const holder = document.createElement('div');
    holder.style.cssText = 'position:fixed;left:-10000px;top:0;background:#fff;padding:0';
    holder.innerHTML = receiptHtml(venta);
    document.body.appendChild(holder);
    const altoMm = Math.ceil(holder.offsetHeight * 25.4 / 96) + 10;
    const margen = (ANCHO_ROLLO - ROLLO.util) / 2;
    try {
      await html2pdf().set({
        margin: [4, margen],
        filename: `boleta-${venta.folio ?? venta.id ?? 'venta'}.pdf`,
        image: { type: 'jpeg', quality: 0.95 },
        html2canvas: { scale: 2.5, backgroundColor: '#ffffff' },
        jsPDF: { unit: 'mm', format: [ANCHO_ROLLO, Math.max(altoMm, ANCHO_ROLLO)], orientation: 'portrait' }
      }).from(holder.firstElementChild).save();
    } finally {
      holder.remove();
    }
  }

  /* ---------- Tallas ---------- */
  const sinTildes = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

  /* Orden natural de tallas: números de menor a mayor, luego XS, S, M, L, XL…, luego el resto */
  const ORDEN_LETRAS = ['xxs', 'xs', 's', 'm', 'l', 'xl', 'xxl', 'xxxl'];
  function claveTalla(t) {
    const n = sinTildes(t);
    if (/^\d+([.,]\d+)?$/.test(n)) return [0, parseFloat(n.replace(',', '.')), ''];
    const i = ORDEN_LETRAS.indexOf(n);
    return i >= 0 ? [1, i, ''] : [2, 0, n];
  }
  function compararTallas(a, b) {
    const x = claveTalla(a), y = claveTalla(b);
    return x[0] - y[0] || x[1] - y[1] || x[2].localeCompare(y[2]);
  }

  /* Carga rápida: crea una prenda en varias tallas y/o suma unidades a tallas existentes.
     datos = { uniforme_id, colegio_id, color_id, nuevas: [{talla_id | talla_nombre, cantidad, precio}],
               sumar: [{inventario_id, cantidad}], clave? } */
  function cargarTallas(datos) {
    return fetch(IMP.cargaTallas, {
      method: 'POST', headers: { 'X-CSRFToken': IMP.csrf, 'Content-Type': 'application/json' }, body: JSON.stringify(datos)
    }).then(r => r.json().then(d => { if (!r.ok) throw new Error(d.message || 'No se pudo guardar'); return d; }));
  }

  /* ---------- A cuánto se vende en internet ----------
     Botones que abren la búsqueda del producto en Google Shopping y Mercado Libre (en otra ventana).
     Sin internet no se muestran: el resto del programa sigue funcionando igual. */
  function enlacesPrecio(texto, { compacto = false } = {}) {
    texto = String(texto ?? '').replace(/\s+/g, ' ').trim();
    if (!texto || !navigator.onLine) return '';
    const q = encodeURIComponent(texto);
    const ml = encodeURIComponent(texto.toLowerCase().replace(/ /g, '-'));
    const google = `https://www.google.com/search?udm=28&gl=cl&hl=es-419&q=${q}`;   // pestaña «Shopping» de Google, en Chile
    const mercado = `https://listado.mercadolibre.cl/${ml}`;
    if (compacto) {
      return `<a class="btn-icon" target="_blank" rel="noopener" href="${google}" title="¿A cuánto se vende? Buscar en Google"><i class="bi bi-google"></i></a>` +
             `<a class="btn-icon" target="_blank" rel="noopener" href="${mercado}" title="¿A cuánto se vende? Buscar en Mercado Libre"><i class="bi bi-bag"></i></a>`;
    }
    return `<span class="d-inline-flex flex-wrap align-items-center gap-1"><span class="small text-secondary me-1"><i class="bi bi-globe2 me-1"></i>¿A cuánto se vende?</span>` +
      `<a class="btn btn-sm btn-light-border" target="_blank" rel="noopener" href="${google}"><i class="bi bi-google me-1"></i>Google</a>` +
      `<a class="btn btn-sm btn-light-border" target="_blank" rel="noopener" href="${mercado}"><i class="bi bi-bag me-1"></i>Mercado Libre</a></span>`;
  }

  /* ---------- Códigos de barras ---------- */
  const JSBARCODE_URL = STATIC + 'vendor/jsbarcode/JsBarcode.all.min.js';

  function esEan13(code) {
    if (!/^\d{13}$/.test(code)) return false;
    const suma = [...code.slice(0, 12)].reduce((a, d, i) => a + Number(d) * (i % 2 ? 3 : 1), 0);
    return (10 - suma % 10) % 10 === Number(code[12]);
  }

  function codigoValido(code) {
    code = String(code ?? '').trim();
    return code !== '' && code !== '0';
  }

  /* Dibuja el código en un <svg>. EAN-13 si es válido; si no, Code128 (acepta cualquier texto). */
  function renderBarcode(svg, code, opts = {}) {
    code = String(code ?? '').trim();
    const base = { margin: 0, height: 60, width: 2, fontSize: 16, textMargin: 2, font: 'Inter, Arial, sans-serif', background: 'transparent' };
    const formato = esEan13(code) ? 'EAN13' : 'CODE128';
    JsBarcode(svg, code, Object.assign(base, { format: formato, flat: formato === 'EAN13' }, opts));
    // Hace que el SVG escale al ancho del contenedor sin deformarse
    const w = svg.getAttribute('width'), h = svg.getAttribute('height');
    if (w && h) {
      svg.setAttribute('viewBox', `0 0 ${parseFloat(w)} ${parseFloat(h)}`);
      svg.removeAttribute('width');
      svg.removeAttribute('height');
    }
    return formato;
  }

  const dtLanguage = {
    processing: 'Cargando…',
    lengthMenu: 'Mostrar _MENU_',
    zeroRecords: 'No se encontraron resultados',
    emptyTable: 'Aún no hay registros',
    info: 'Mostrando _START_–_END_ de _TOTAL_',
    infoEmpty: 'Sin registros',
    infoFiltered: '(filtrado de _MAX_)',
    loadingRecords: 'Cargando…',
    paginate: { first: '«', last: '»', next: '›', previous: '‹' }
  };

  return {
    money, num, esc, toast, formatDateTime, dtLanguage, loadScript, METODOS_PAGO,
    receiptHtml, printReceipt, downloadReceipt, estadoImpresora, verificarImpresora, instalarDriver, nombreImpresora, compararTallas, cargarTallas, enlacesPrecio, armarConjuntos, lineasBoleta,
    JSBARCODE_URL, renderBarcode, esEan13, codigoValido
  };
})();

/* Reloj, menú lateral móvil */
document.addEventListener('DOMContentLoaded', function () {
  const clock = document.getElementById('topbar-clock');
  if (clock) {
    const tick = () => {
      const d = new Date();
      clock.innerHTML = `<strong>${d.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}</strong>` +
        d.toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'long' });
    };
    tick();
    setInterval(tick, 15000);
  }

  document.querySelectorAll('[data-toggle-sidebar]').forEach(b =>
    b.addEventListener('click', () => document.body.classList.toggle('sidebar-open')));

  // Menú compacto: el botón guarda la preferencia; sin preferencia se ajusta solo al ancho de la pantalla
  const root = document.documentElement;
  const railBtn = document.getElementById('rail-toggle');
  const leerPref = () => { try { return localStorage.getItem('sidebar_rail'); } catch (e) { return null; } };
  if (railBtn) {
    railBtn.addEventListener('click', () => {
      const rail = !root.classList.contains('rail');
      root.classList.toggle('rail', rail);
      try { localStorage.setItem('sidebar_rail', rail ? '1' : '0'); } catch (e) {}
      window.dispatchEvent(new Event('resize'));   // para que gráficos y tablas se reacomoden
    });
  }
  window.addEventListener('resize', () => {
    if (leerPref() === null) root.classList.toggle('rail', window.innerWidth < 1280);
  });

  // Selector de sección: el logo del menú despliega los círculos de uniformes, librería y egresos
  const selector = document.getElementById('sec-switch');
  const btnLogo = document.getElementById('brand-switch');
  if (selector && btnLogo) {
    const cerrarSelector = () => {
      selector.classList.remove('abierto');
      btnLogo.setAttribute('aria-expanded', 'false');
      setTimeout(() => { if (!selector.classList.contains('abierto')) selector.hidden = true; }, 300);
    };
    btnLogo.addEventListener('click', () => {
      selector.hidden = false;
      requestAnimationFrame(() => requestAnimationFrame(() => selector.classList.add('abierto')));   // así se anima la salida
      btnLogo.setAttribute('aria-expanded', 'true');
      const primera = selector.querySelector('.sec-otra');
      if (primera) setTimeout(() => primera.focus({ preventScroll: true }), 50);
    });
    selector.addEventListener('click', e => { if (e.target.closest('[data-sec-cerrar]')) cerrarSelector(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !selector.hidden) cerrarSelector(); });
  }

  // DataTables: oculta la paginación cuando cabe todo en una página
  if (window.jQuery) {
    jQuery(document).on('draw.dt', function (e, settings) {
      const api = new jQuery.fn.dataTable.Api(settings);
      jQuery(api.table().container()).find('.dataTables_paginate').toggle(api.page.info().pages > 1);
    });
  }
});
