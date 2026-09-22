(() => {
  const ns = 'http://www.w3.org/2000/svg';
  const reference = document.getElementById('reference-spots');
  const measured = document.getElementById('measured-spots');
  const description = document.getElementById('mode-description');
  const modes = {
    flat: 'φ = 0',
    tilt: 'φ ∝ 11x + 6y',
    defocus: 'Z₄ = 2(x² + y²) − 1',
    astigmatism: 'Z₆ = x² − y²',
    coma: 'Z₈ = x[3(x² + y²) − 2]'
  };
  const xSquared = '<msup><mi>x</mi><mn>2</mn></msup>';
  const ySquared = '<msup><mi>y</mi><mn>2</mn></msup>';
  const radiusSquared = `<mrow><mo>(</mo>${xSquared}<mo>+</mo>${ySquared}<mo>)</mo></mrow>`;
  const zernike = index => `<msub class="equation-symbol"><mi>Z</mi><mn>${index}</mn></msub><mo>=</mo>`;
  const equations = {
    flat: '<mi class="equation-symbol">φ</mi><mo>=</mo><mn>0</mn>',
    tilt: '<mi class="equation-symbol">φ</mi><mo>∝</mo><mn>11</mn><mi>x</mi><mo>+</mo><mn>6</mn><mi>y</mi>',
    defocus: `${zernike(4)}<mn>2</mn>${radiusSquared}<mo>−</mo><mn>1</mn>`,
    astigmatism: `${zernike(6)}${xSquared}<mo>−</mo>${ySquared}`,
    coma: `${zernike(8)}<mi>x</mi><mrow><mo>[</mo><mn>3</mn>${radiusSquared}<mo>−</mo><mn>2</mn><mo>]</mo></mrow>`
  };
  function spotOffset(mode, row, col) {
    // Spot displacement follows the local wavefront gradient.
    // Optical y points up; SVG y points down. Normalization is in the display gain.
    const x = col / 4.6;
    const y = -row / 4.6;
    switch (mode) {
      case 'tilt': return [11, -6];
      case 'defocus': return [col * 2.5, row * 2.5];
      // W proportional to x^2-y^2; gradient = (2x, -2y).
      case 'astigmatism': return [col * 2.5, -row * 2.5];
      // W proportional to (3(x^2+y^2)-2)x; gradient = (9x^2+3y^2-2, 6xy).
      case 'coma': return [3.5 * (9*x*x + 3*y*y - 2), -3.5 * 6*x*y];
      default: return [0, 0];
    }
  }
  const spots = [];
  function circle(parent, attributes) {
    const element = document.createElementNS(ns, 'circle');
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    parent.appendChild(element);
    return element;
  }
  for (let row = -4; row <= 4; row++) {
    for (let col = -4; col <= 4; col++) {
      if (Math.hypot(row, col) > 4.6) continue;
      const x = 240 + col * 36;
      const y = 195 + row * 36;
      circle(reference, { cx: x, cy: y, r: 4.5, fill: 'none', stroke: '#728698', 'stroke-opacity': .48, 'stroke-width': .8 });
      const group = document.createElementNS(ns, 'g');
      group.style.transform = 'translate(0px, 0px)';
      measured.appendChild(group);
      const color = col + row > 1 ? '#e7b284' : col + row < -2 ? '#a99cdb' : '#9ce6da';
      circle(group, { cx: x, cy: y, r: 4, fill: color, opacity: .65, filter: 'url(#spot-glow)' });
      circle(group, { cx: x, cy: y, r: 2.2, fill: color });
      circle(group, { cx: x, cy: y, r: .8, fill: '#fff9e9' });
      spots.push({ group, row, col });
    }
  }
  document.querySelectorAll('[data-mode]').forEach(button => {
    button.addEventListener('click', () => {
      const mode = button.dataset.mode;
      document.querySelectorAll('[data-mode]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      spots.forEach(({ group, row, col }) => {
        // Qualitative illustration only: these offsets are not reconstructed measurements.
        const [dx, dy] = spotOffset(mode, row, col);
        group.style.transform = `translate(${dx}px, ${dy}px)`;
      });
      // All markup comes from the fixed equations above; no external input.
      description.innerHTML = `<math xmlns="http://www.w3.org/1998/Math/MathML" display="block" aria-label="${modes[mode]}"><mrow>${equations[mode]}</mrow></math>`;
      document.getElementById('field-desc').textContent = modes[mode] + ' Illustrated spot displacements, not measured data.';
    });
  });
})();
