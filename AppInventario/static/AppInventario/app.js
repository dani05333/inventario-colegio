/* Chloe Creaciones · POS — utilidades compartidas */

const App = (function () {
  // Ruta de los archivos estáticos (la define la plantilla); todo se sirve localmente, sin internet
  const STATIC = window.APP_STATIC || '/static/';
  const moneyFmt = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });
  const numFmt = new Intl.NumberFormat('es-CL');

  function money(v) { return moneyFmt.format(Math.round(Number(v) || 0)); }
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

  /* ---------- Datos del negocio que salen en la boleta (edítalos aquí) ---------- */
  const NEGOCIO = {
    nombre: 'Chloe Creaciones',
    bajada: 'Uniformes escolares',
    lineas: [
      // 'RUT: 12.345.678-9',
      // 'Av. Siempre Viva 123, Santiago',
      // 'Tel: +56 9 1234 5678',
    ],
    pie: '¡Gracias por su compra!',
  };

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
    const rows = lineasBoleta(venta).map(i => `
      <tr><td colspan="2"><strong>${esc(i.nombre)} · T. ${esc(i.talla)}</strong></td></tr>
      <tr><td>&nbsp;&nbsp;${i.cantidad} x ${money(i.precio)}<br>&nbsp;&nbsp;<small>${esc(i.tipo === 'conjunto' ? i.detalle : i.colegio)}</small></td><td class="r">${money(i.subtotal)}</td></tr>`).join('');
    // La forma de pago no se imprime en la boleta; solo el vuelto cuando se pagó en efectivo
    const pago = venta.recibido ? `
      <tr><td>Recibido</td><td class="r">${money(venta.recibido)}</td></tr>
      <tr><td>Vuelto</td><td class="r">${money(venta.vuelto)}</td></tr>` : '';
    const unidades = venta.items.reduce((a, i) => a + i.cantidad, 0);
    return `
      <div class="receipt">
        <h3>${esc(NEGOCIO.nombre)}</h3>
        <div class="center">${esc(NEGOCIO.bajada)}</div>
        ${NEGOCIO.lineas.map(l => `<div class="center">${esc(l)}</div>`).join('')}
        <hr>
        <div><strong>Boleta N° ${esc(venta.id ?? '—')}</strong></div>
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
        </table>
        <hr>
        <div class="center">${esc(NEGOCIO.pie)}</div>
      </div>`;
  }

  function printReceipt(venta) {
    document.getElementById('print-area').innerHTML = receiptHtml(venta);
    window.print();
  }

  /* Descarga la boleta como PDF en formato de rollo de 80 mm */
  async function downloadReceipt(venta) {
    try {
      await loadScript(STATIC + 'vendor/html2pdf/html2pdf.bundle.min.js');
    } catch (e) {
      toast('No se pudo preparar el PDF (¿hay conexión a internet?)', 'error');
      return;
    }
    const holder = document.createElement('div');
    holder.style.cssText = 'position:fixed;left:-10000px;top:0;width:272px;background:#fff;padding:0';
    holder.innerHTML = receiptHtml(venta);
    holder.firstElementChild.style.width = '272px';
    document.body.appendChild(holder);
    const altoMm = Math.ceil(holder.offsetHeight * 25.4 / 96) + 10;
    try {
      await html2pdf().set({
        margin: 4,
        filename: `boleta-${venta.id ?? 'venta'}.pdf`,
        image: { type: 'jpeg', quality: 0.95 },
        html2canvas: { scale: 2.5, backgroundColor: '#ffffff' },
        jsPDF: { unit: 'mm', format: [80, Math.max(altoMm, 80)], orientation: 'portrait' }
      }).from(holder.firstElementChild).save();
    } finally {
      holder.remove();
    }
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
    receiptHtml, printReceipt, downloadReceipt, armarConjuntos, lineasBoleta,
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

  // DataTables: oculta la paginación cuando cabe todo en una página
  if (window.jQuery) {
    jQuery(document).on('draw.dt', function (e, settings) {
      const api = new jQuery.fn.dataTable.Api(settings);
      jQuery(api.table().container()).find('.dataTables_paginate').toggle(api.page.info().pages > 1);
    });
  }
});
