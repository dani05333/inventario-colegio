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

  /* ---------- Boleta ----------
     venta = { id, fecha, total, items: [{nombre, talla, colegio, cantidad, precio, subtotal}], recibido?, vuelto? } */
  function receiptHtml(venta) {
    const rows = venta.items.map(i => `
      <tr><td colspan="2"><strong>${esc(i.nombre)} · T. ${esc(i.talla)}</strong></td></tr>
      <tr><td>&nbsp;&nbsp;${i.cantidad} x ${money(i.precio)}<br>&nbsp;&nbsp;<small>${esc(i.colegio)}</small></td><td class="r">${money(i.subtotal)}</td></tr>`).join('');
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
    receiptHtml, printReceipt, downloadReceipt,
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
