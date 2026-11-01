/* Savant-Card upstream: c2030b1a42e466bc5cccf69735eea0ca89c82c9e; see Savant-Card.LICENSE */
(function () {
if (customElements.get("savant-energy-breaker-board-card")) return;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const pe = globalThis, Se = pe.ShadowRoot && (pe.ShadyCSS === void 0 || pe.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype, Ae = Symbol(), Oe = /* @__PURE__ */ new WeakMap();
let qe = class {
  constructor(e, s, r) {
    if (this._$cssResult$ = !0, r !== Ae) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = e, this.t = s;
  }
  get styleSheet() {
    let e = this.o;
    const s = this.t;
    if (Se && e === void 0) {
      const r = s !== void 0 && s.length === 1;
      r && (e = Oe.get(s)), e === void 0 && ((this.o = e = new CSSStyleSheet()).replaceSync(this.cssText), r && Oe.set(s, e));
    }
    return e;
  }
  toString() {
    return this.cssText;
  }
};
const gt = (t) => new qe(typeof t == "string" ? t : t + "", void 0, Ae), k = (t, ...e) => {
  const s = t.length === 1 ? t[0] : e.reduce((r, i, a) => r + ((o) => {
    if (o._$cssResult$ === !0) return o.cssText;
    if (typeof o == "number") return o;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + o + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(i) + t[a + 1], t[0]);
  return new qe(s, t, Ae);
}, vt = (t, e) => {
  if (Se) t.adoptedStyleSheets = e.map((s) => s instanceof CSSStyleSheet ? s : s.styleSheet);
  else for (const s of e) {
    const r = document.createElement("style"), i = pe.litNonce;
    i !== void 0 && r.setAttribute("nonce", i), r.textContent = s.cssText, t.appendChild(r);
  }
}, Le = Se ? (t) => t : (t) => t instanceof CSSStyleSheet ? ((e) => {
  let s = "";
  for (const r of e.cssRules) s += r.cssText;
  return gt(s);
})(t) : t;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const { is: mt, defineProperty: ft, getOwnPropertyDescriptor: bt, getOwnPropertyNames: yt, getOwnPropertySymbols: wt, getPrototypeOf: xt } = Object, T = globalThis, Ne = T.trustedTypes, _t = Ne ? Ne.emptyScript : "", we = T.reactiveElementPolyfillSupport, ee = (t, e) => t, ue = { toAttribute(t, e) {
  switch (e) {
    case Boolean:
      t = t ? _t : null;
      break;
    case Object:
    case Array:
      t = t == null ? t : JSON.stringify(t);
  }
  return t;
}, fromAttribute(t, e) {
  let s = t;
  switch (e) {
    case Boolean:
      s = t !== null;
      break;
    case Number:
      s = t === null ? null : Number(t);
      break;
    case Object:
    case Array:
      try {
        s = JSON.parse(t);
      } catch {
        s = null;
      }
  }
  return s;
} }, Ce = (t, e) => !mt(t, e), Be = { attribute: !0, type: String, converter: ue, reflect: !1, useDefault: !1, hasChanged: Ce };
Symbol.metadata ?? (Symbol.metadata = Symbol("metadata")), T.litPropertyMetadata ?? (T.litPropertyMetadata = /* @__PURE__ */ new WeakMap());
let q = class extends HTMLElement {
  static addInitializer(e) {
    this._$Ei(), (this.l ?? (this.l = [])).push(e);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(e, s = Be) {
    if (s.state && (s.attribute = !1), this._$Ei(), this.prototype.hasOwnProperty(e) && ((s = Object.create(s)).wrapped = !0), this.elementProperties.set(e, s), !s.noAccessor) {
      const r = Symbol(), i = this.getPropertyDescriptor(e, r, s);
      i !== void 0 && ft(this.prototype, e, i);
    }
  }
  static getPropertyDescriptor(e, s, r) {
    const { get: i, set: a } = bt(this.prototype, e) ?? { get() {
      return this[s];
    }, set(o) {
      this[s] = o;
    } };
    return { get: i, set(o) {
      const n = i == null ? void 0 : i.call(this);
      a == null || a.call(this, o), this.requestUpdate(e, n, r);
    }, configurable: !0, enumerable: !0 };
  }
  static getPropertyOptions(e) {
    return this.elementProperties.get(e) ?? Be;
  }
  static _$Ei() {
    if (this.hasOwnProperty(ee("elementProperties"))) return;
    const e = xt(this);
    e.finalize(), e.l !== void 0 && (this.l = [...e.l]), this.elementProperties = new Map(e.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(ee("finalized"))) return;
    if (this.finalized = !0, this._$Ei(), this.hasOwnProperty(ee("properties"))) {
      const s = this.properties, r = [...yt(s), ...wt(s)];
      for (const i of r) this.createProperty(i, s[i]);
    }
    const e = this[Symbol.metadata];
    if (e !== null) {
      const s = litPropertyMetadata.get(e);
      if (s !== void 0) for (const [r, i] of s) this.elementProperties.set(r, i);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [s, r] of this.elementProperties) {
      const i = this._$Eu(s, r);
      i !== void 0 && this._$Eh.set(i, s);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(e) {
    const s = [];
    if (Array.isArray(e)) {
      const r = new Set(e.flat(1 / 0).reverse());
      for (const i of r) s.unshift(Le(i));
    } else e !== void 0 && s.push(Le(e));
    return s;
  }
  static _$Eu(e, s) {
    const r = s.attribute;
    return r === !1 ? void 0 : typeof r == "string" ? r : typeof e == "string" ? e.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = !1, this.hasUpdated = !1, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    var e;
    this._$ES = new Promise((s) => this.enableUpdating = s), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), (e = this.constructor.l) == null || e.forEach((s) => s(this));
  }
  addController(e) {
    var s;
    (this._$EO ?? (this._$EO = /* @__PURE__ */ new Set())).add(e), this.renderRoot !== void 0 && this.isConnected && ((s = e.hostConnected) == null || s.call(e));
  }
  removeController(e) {
    var s;
    (s = this._$EO) == null || s.delete(e);
  }
  _$E_() {
    const e = /* @__PURE__ */ new Map(), s = this.constructor.elementProperties;
    for (const r of s.keys()) this.hasOwnProperty(r) && (e.set(r, this[r]), delete this[r]);
    e.size > 0 && (this._$Ep = e);
  }
  createRenderRoot() {
    const e = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return vt(e, this.constructor.elementStyles), e;
  }
  connectedCallback() {
    var e;
    this.renderRoot ?? (this.renderRoot = this.createRenderRoot()), this.enableUpdating(!0), (e = this._$EO) == null || e.forEach((s) => {
      var r;
      return (r = s.hostConnected) == null ? void 0 : r.call(s);
    });
  }
  enableUpdating(e) {
  }
  disconnectedCallback() {
    var e;
    (e = this._$EO) == null || e.forEach((s) => {
      var r;
      return (r = s.hostDisconnected) == null ? void 0 : r.call(s);
    });
  }
  attributeChangedCallback(e, s, r) {
    this._$AK(e, r);
  }
  _$ET(e, s) {
    var a;
    const r = this.constructor.elementProperties.get(e), i = this.constructor._$Eu(e, r);
    if (i !== void 0 && r.reflect === !0) {
      const o = (((a = r.converter) == null ? void 0 : a.toAttribute) !== void 0 ? r.converter : ue).toAttribute(s, r.type);
      this._$Em = e, o == null ? this.removeAttribute(i) : this.setAttribute(i, o), this._$Em = null;
    }
  }
  _$AK(e, s) {
    var a, o;
    const r = this.constructor, i = r._$Eh.get(e);
    if (i !== void 0 && this._$Em !== i) {
      const n = r.getPropertyOptions(i), l = typeof n.converter == "function" ? { fromAttribute: n.converter } : ((a = n.converter) == null ? void 0 : a.fromAttribute) !== void 0 ? n.converter : ue;
      this._$Em = i;
      const c = l.fromAttribute(s, n.type);
      this[i] = c ?? ((o = this._$Ej) == null ? void 0 : o.get(i)) ?? c, this._$Em = null;
    }
  }
  requestUpdate(e, s, r, i = !1, a) {
    var o;
    if (e !== void 0) {
      const n = this.constructor;
      if (i === !1 && (a = this[e]), r ?? (r = n.getPropertyOptions(e)), !((r.hasChanged ?? Ce)(a, s) || r.useDefault && r.reflect && a === ((o = this._$Ej) == null ? void 0 : o.get(e)) && !this.hasAttribute(n._$Eu(e, r)))) return;
      this.C(e, s, r);
    }
    this.isUpdatePending === !1 && (this._$ES = this._$EP());
  }
  C(e, s, { useDefault: r, reflect: i, wrapped: a }, o) {
    r && !(this._$Ej ?? (this._$Ej = /* @__PURE__ */ new Map())).has(e) && (this._$Ej.set(e, o ?? s ?? this[e]), a !== !0 || o !== void 0) || (this._$AL.has(e) || (this.hasUpdated || r || (s = void 0), this._$AL.set(e, s)), i === !0 && this._$Em !== e && (this._$Eq ?? (this._$Eq = /* @__PURE__ */ new Set())).add(e));
  }
  async _$EP() {
    this.isUpdatePending = !0;
    try {
      await this._$ES;
    } catch (s) {
      Promise.reject(s);
    }
    const e = this.scheduleUpdate();
    return e != null && await e, !this.isUpdatePending;
  }
  scheduleUpdate() {
    return this.performUpdate();
  }
  performUpdate() {
    var r;
    if (!this.isUpdatePending) return;
    if (!this.hasUpdated) {
      if (this.renderRoot ?? (this.renderRoot = this.createRenderRoot()), this._$Ep) {
        for (const [a, o] of this._$Ep) this[a] = o;
        this._$Ep = void 0;
      }
      const i = this.constructor.elementProperties;
      if (i.size > 0) for (const [a, o] of i) {
        const { wrapped: n } = o, l = this[a];
        n !== !0 || this._$AL.has(a) || l === void 0 || this.C(a, void 0, o, l);
      }
    }
    let e = !1;
    const s = this._$AL;
    try {
      e = this.shouldUpdate(s), e ? (this.willUpdate(s), (r = this._$EO) == null || r.forEach((i) => {
        var a;
        return (a = i.hostUpdate) == null ? void 0 : a.call(i);
      }), this.update(s)) : this._$EM();
    } catch (i) {
      throw e = !1, this._$EM(), i;
    }
    e && this._$AE(s);
  }
  willUpdate(e) {
  }
  _$AE(e) {
    var s;
    (s = this._$EO) == null || s.forEach((r) => {
      var i;
      return (i = r.hostUpdated) == null ? void 0 : i.call(r);
    }), this.hasUpdated || (this.hasUpdated = !0, this.firstUpdated(e)), this.updated(e);
  }
  _$EM() {
    this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = !1;
  }
  get updateComplete() {
    return this.getUpdateComplete();
  }
  getUpdateComplete() {
    return this._$ES;
  }
  shouldUpdate(e) {
    return !0;
  }
  update(e) {
    this._$Eq && (this._$Eq = this._$Eq.forEach((s) => this._$ET(s, this[s]))), this._$EM();
  }
  updated(e) {
  }
  firstUpdated(e) {
  }
};
q.elementStyles = [], q.shadowRootOptions = { mode: "open" }, q[ee("elementProperties")] = /* @__PURE__ */ new Map(), q[ee("finalized")] = /* @__PURE__ */ new Map(), we == null || we({ ReactiveElement: q }), (T.reactiveElementVersions ?? (T.reactiveElementVersions = [])).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const te = globalThis, He = (t) => t, ge = te.trustedTypes, Te = ge ? ge.createPolicy("lit-html", { createHTML: (t) => t }) : void 0, Ge = "$lit$", H = `lit$${Math.random().toFixed(9).slice(2)}$`, Qe = "?" + H, $t = `<${Qe}>`, W = document, ae = () => W.createComment(""), oe = (t) => t === null || typeof t != "object" && typeof t != "function", Pe = Array.isArray, kt = (t) => Pe(t) || typeof (t == null ? void 0 : t[Symbol.iterator]) == "function", xe = `[ 	
\f\r]`, X = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g, De = /-->/g, ze = />/g, I = RegExp(`>|${xe}(?:([^\\s"'>=/]+)(${xe}*=${xe}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g"), je = /'/g, Re = /"/g, Ye = /^(?:script|style|textarea|title)$/i, Xe = (t) => (e, ...s) => ({ _$litType$: t, strings: e, values: s }), h = Xe(1), se = Xe(2), G = Symbol.for("lit-noChange"), v = Symbol.for("lit-nothing"), Ie = /* @__PURE__ */ new WeakMap(), F = W.createTreeWalker(W, 129);
function Je(t, e) {
  if (!Pe(t) || !t.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return Te !== void 0 ? Te.createHTML(e) : e;
}
const St = (t, e) => {
  const s = t.length - 1, r = [];
  let i, a = e === 2 ? "<svg>" : e === 3 ? "<math>" : "", o = X;
  for (let n = 0; n < s; n++) {
    const l = t[n];
    let c, u, p = -1, m = 0;
    for (; m < l.length && (o.lastIndex = m, u = o.exec(l), u !== null); ) m = o.lastIndex, o === X ? u[1] === "!--" ? o = De : u[1] !== void 0 ? o = ze : u[2] !== void 0 ? (Ye.test(u[2]) && (i = RegExp("</" + u[2], "g")), o = I) : u[3] !== void 0 && (o = I) : o === I ? u[0] === ">" ? (o = i ?? X, p = -1) : u[1] === void 0 ? p = -2 : (p = o.lastIndex - u[2].length, c = u[1], o = u[3] === void 0 ? I : u[3] === '"' ? Re : je) : o === Re || o === je ? o = I : o === De || o === ze ? o = X : (o = I, i = void 0);
    const _ = o === I && t[n + 1].startsWith("/>") ? " " : "";
    a += o === X ? l + $t : p >= 0 ? (r.push(c), l.slice(0, p) + Ge + l.slice(p) + H + _) : l + H + (p === -2 ? n : _);
  }
  return [Je(t, a + (t[s] || "<?>") + (e === 2 ? "</svg>" : e === 3 ? "</math>" : "")), r];
};
class ne {
  constructor({ strings: e, _$litType$: s }, r) {
    let i;
    this.parts = [];
    let a = 0, o = 0;
    const n = e.length - 1, l = this.parts, [c, u] = St(e, s);
    if (this.el = ne.createElement(c, r), F.currentNode = this.el.content, s === 2 || s === 3) {
      const p = this.el.content.firstChild;
      p.replaceWith(...p.childNodes);
    }
    for (; (i = F.nextNode()) !== null && l.length < n; ) {
      if (i.nodeType === 1) {
        if (i.hasAttributes()) for (const p of i.getAttributeNames()) if (p.endsWith(Ge)) {
          const m = u[o++], _ = i.getAttribute(p).split(H), S = /([.?@])?(.*)/.exec(m);
          l.push({ type: 1, index: a, name: S[2], strings: _, ctor: S[1] === "." ? Ct : S[1] === "?" ? Pt : S[1] === "@" ? Mt : be }), i.removeAttribute(p);
        } else p.startsWith(H) && (l.push({ type: 6, index: a }), i.removeAttribute(p));
        if (Ye.test(i.tagName)) {
          const p = i.textContent.split(H), m = p.length - 1;
          if (m > 0) {
            i.textContent = ge ? ge.emptyScript : "";
            for (let _ = 0; _ < m; _++) i.append(p[_], ae()), F.nextNode(), l.push({ type: 2, index: ++a });
            i.append(p[m], ae());
          }
        }
      } else if (i.nodeType === 8) if (i.data === Qe) l.push({ type: 2, index: a });
      else {
        let p = -1;
        for (; (p = i.data.indexOf(H, p + 1)) !== -1; ) l.push({ type: 7, index: a }), p += H.length - 1;
      }
      a++;
    }
  }
  static createElement(e, s) {
    const r = W.createElement("template");
    return r.innerHTML = e, r;
  }
}
function Q(t, e, s = t, r) {
  var o, n;
  if (e === G) return e;
  let i = r !== void 0 ? (o = s._$Co) == null ? void 0 : o[r] : s._$Cl;
  const a = oe(e) ? void 0 : e._$litDirective$;
  return (i == null ? void 0 : i.constructor) !== a && ((n = i == null ? void 0 : i._$AO) == null || n.call(i, !1), a === void 0 ? i = void 0 : (i = new a(t), i._$AT(t, s, r)), r !== void 0 ? (s._$Co ?? (s._$Co = []))[r] = i : s._$Cl = i), i !== void 0 && (e = Q(t, i._$AS(t, e.values), i, r)), e;
}
class At {
  constructor(e, s) {
    this._$AV = [], this._$AN = void 0, this._$AD = e, this._$AM = s;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(e) {
    const { el: { content: s }, parts: r } = this._$AD, i = ((e == null ? void 0 : e.creationScope) ?? W).importNode(s, !0);
    F.currentNode = i;
    let a = F.nextNode(), o = 0, n = 0, l = r[0];
    for (; l !== void 0; ) {
      if (o === l.index) {
        let c;
        l.type === 2 ? c = new de(a, a.nextSibling, this, e) : l.type === 1 ? c = new l.ctor(a, l.name, l.strings, this, e) : l.type === 6 && (c = new Et(a, this, e)), this._$AV.push(c), l = r[++n];
      }
      o !== (l == null ? void 0 : l.index) && (a = F.nextNode(), o++);
    }
    return F.currentNode = W, i;
  }
  p(e) {
    let s = 0;
    for (const r of this._$AV) r !== void 0 && (r.strings !== void 0 ? (r._$AI(e, r, s), s += r.strings.length - 2) : r._$AI(e[s])), s++;
  }
}
class de {
  get _$AU() {
    var e;
    return ((e = this._$AM) == null ? void 0 : e._$AU) ?? this._$Cv;
  }
  constructor(e, s, r, i) {
    this.type = 2, this._$AH = v, this._$AN = void 0, this._$AA = e, this._$AB = s, this._$AM = r, this.options = i, this._$Cv = (i == null ? void 0 : i.isConnected) ?? !0;
  }
  get parentNode() {
    let e = this._$AA.parentNode;
    const s = this._$AM;
    return s !== void 0 && (e == null ? void 0 : e.nodeType) === 11 && (e = s.parentNode), e;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(e, s = this) {
    e = Q(this, e, s), oe(e) ? e === v || e == null || e === "" ? (this._$AH !== v && this._$AR(), this._$AH = v) : e !== this._$AH && e !== G && this._(e) : e._$litType$ !== void 0 ? this.$(e) : e.nodeType !== void 0 ? this.T(e) : kt(e) ? this.k(e) : this._(e);
  }
  O(e) {
    return this._$AA.parentNode.insertBefore(e, this._$AB);
  }
  T(e) {
    this._$AH !== e && (this._$AR(), this._$AH = this.O(e));
  }
  _(e) {
    this._$AH !== v && oe(this._$AH) ? this._$AA.nextSibling.data = e : this.T(W.createTextNode(e)), this._$AH = e;
  }
  $(e) {
    var a;
    const { values: s, _$litType$: r } = e, i = typeof r == "number" ? this._$AC(e) : (r.el === void 0 && (r.el = ne.createElement(Je(r.h, r.h[0]), this.options)), r);
    if (((a = this._$AH) == null ? void 0 : a._$AD) === i) this._$AH.p(s);
    else {
      const o = new At(i, this), n = o.u(this.options);
      o.p(s), this.T(n), this._$AH = o;
    }
  }
  _$AC(e) {
    let s = Ie.get(e.strings);
    return s === void 0 && Ie.set(e.strings, s = new ne(e)), s;
  }
  k(e) {
    Pe(this._$AH) || (this._$AH = [], this._$AR());
    const s = this._$AH;
    let r, i = 0;
    for (const a of e) i === s.length ? s.push(r = new de(this.O(ae()), this.O(ae()), this, this.options)) : r = s[i], r._$AI(a), i++;
    i < s.length && (this._$AR(r && r._$AB.nextSibling, i), s.length = i);
  }
  _$AR(e = this._$AA.nextSibling, s) {
    var r;
    for ((r = this._$AP) == null ? void 0 : r.call(this, !1, !0, s); e !== this._$AB; ) {
      const i = He(e).nextSibling;
      He(e).remove(), e = i;
    }
  }
  setConnected(e) {
    var s;
    this._$AM === void 0 && (this._$Cv = e, (s = this._$AP) == null || s.call(this, e));
  }
}
class be {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(e, s, r, i, a) {
    this.type = 1, this._$AH = v, this._$AN = void 0, this.element = e, this.name = s, this._$AM = i, this.options = a, r.length > 2 || r[0] !== "" || r[1] !== "" ? (this._$AH = Array(r.length - 1).fill(new String()), this.strings = r) : this._$AH = v;
  }
  _$AI(e, s = this, r, i) {
    const a = this.strings;
    let o = !1;
    if (a === void 0) e = Q(this, e, s, 0), o = !oe(e) || e !== this._$AH && e !== G, o && (this._$AH = e);
    else {
      const n = e;
      let l, c;
      for (e = a[0], l = 0; l < a.length - 1; l++) c = Q(this, n[r + l], s, l), c === G && (c = this._$AH[l]), o || (o = !oe(c) || c !== this._$AH[l]), c === v ? e = v : e !== v && (e += (c ?? "") + a[l + 1]), this._$AH[l] = c;
    }
    o && !i && this.j(e);
  }
  j(e) {
    e === v ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, e ?? "");
  }
}
class Ct extends be {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(e) {
    this.element[this.name] = e === v ? void 0 : e;
  }
}
class Pt extends be {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(e) {
    this.element.toggleAttribute(this.name, !!e && e !== v);
  }
}
class Mt extends be {
  constructor(e, s, r, i, a) {
    super(e, s, r, i, a), this.type = 5;
  }
  _$AI(e, s = this) {
    if ((e = Q(this, e, s, 0) ?? v) === G) return;
    const r = this._$AH, i = e === v && r !== v || e.capture !== r.capture || e.once !== r.once || e.passive !== r.passive, a = e !== v && (r === v || i);
    i && this.element.removeEventListener(this.name, this, r), a && this.element.addEventListener(this.name, this, e), this._$AH = e;
  }
  handleEvent(e) {
    var s;
    typeof this._$AH == "function" ? this._$AH.call(((s = this.options) == null ? void 0 : s.host) ?? this.element, e) : this._$AH.handleEvent(e);
  }
}
class Et {
  constructor(e, s, r) {
    this.element = e, this.type = 6, this._$AN = void 0, this._$AM = s, this.options = r;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(e) {
    Q(this, e);
  }
}
const _e = te.litHtmlPolyfillSupport;
_e == null || _e(ne, de), (te.litHtmlVersions ?? (te.litHtmlVersions = [])).push("3.3.3");
const Ot = (t, e, s) => {
  const r = (s == null ? void 0 : s.renderBefore) ?? e;
  let i = r._$litPart$;
  if (i === void 0) {
    const a = (s == null ? void 0 : s.renderBefore) ?? null;
    r._$litPart$ = i = new de(e.insertBefore(ae(), a), a, void 0, s ?? {});
  }
  return i._$AI(t), i;
};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const V = globalThis;
class y extends q {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    var s;
    const e = super.createRenderRoot();
    return (s = this.renderOptions).renderBefore ?? (s.renderBefore = e.firstChild), e;
  }
  update(e) {
    const s = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(e), this._$Do = Ot(s, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    var e;
    super.connectedCallback(), (e = this._$Do) == null || e.setConnected(!0);
  }
  disconnectedCallback() {
    var e;
    super.disconnectedCallback(), (e = this._$Do) == null || e.setConnected(!1);
  }
  render() {
    return G;
  }
}
var Ze;
y._$litElement$ = !0, y.finalized = !0, (Ze = V.litElementHydrateSupport) == null || Ze.call(V, { LitElement: y });
const $e = V.litElementPolyfillSupport;
$e == null || $e({ LitElement: y });
(V.litElementVersions ?? (V.litElementVersions = [])).push("4.2.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const C = (t) => (e, s) => {
  s !== void 0 ? s.addInitializer(() => {
    customElements.define(t, e);
  }) : customElements.define(t, e);
};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const Lt = { attribute: !0, type: String, converter: ue, reflect: !1, hasChanged: Ce }, Nt = (t = Lt, e, s) => {
  const { kind: r, metadata: i } = s;
  let a = globalThis.litPropertyMetadata.get(i);
  if (a === void 0 && globalThis.litPropertyMetadata.set(i, a = /* @__PURE__ */ new Map()), r === "setter" && ((t = Object.create(t)).wrapped = !0), a.set(s.name, t), r === "accessor") {
    const { name: o } = s;
    return { set(n) {
      const l = e.get.call(this);
      e.set.call(this, n), this.requestUpdate(o, l, t, !0, n);
    }, init(n) {
      return n !== void 0 && this.C(o, void 0, t, n), n;
    } };
  }
  if (r === "setter") {
    const { name: o } = s;
    return function(n) {
      const l = this[o];
      e.call(this, n), this.requestUpdate(o, l, t, !0, n);
    };
  }
  throw Error("Unsupported decorator location: " + r);
};
function d(t) {
  return (e, s) => typeof s == "object" ? Nt(t, e, s) : ((r, i, a) => {
    const o = i.hasOwnProperty(a);
    return i.constructor.createProperty(a, r), o ? Object.getOwnPropertyDescriptor(i, a) : void 0;
  })(t, e, s);
}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
function g(t) {
  return d({ ...t, state: !0, attribute: !1 });
}
var Bt = Object.defineProperty, Ht = Object.getOwnPropertyDescriptor, Me = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? Ht(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && Bt(e, s, i), i;
};
let le = class extends y {
  constructor() {
    super(...arguments), this.points = [], this.state = "normal";
  }
  render() {
    const t = Tt(this.points), e = t ?? Dt(), s = !t;
    return se`
      <svg
        data-no-history=${s ? "true" : "false"}
        viewBox="0 0 100 36"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="savant-sparkline-area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="currentColor" stop-opacity="0.44"></stop>
            <stop offset="50%" stop-color="currentColor" stop-opacity="0.16"></stop>
            <stop offset="100%" stop-color="currentColor" stop-opacity="0"></stop>
          </linearGradient>
        </defs>
        ${s ? "" : se`
              ${e.fillPath ? se`<path class="fill-base" d=${e.fillPath}></path>` : ""}
            `}
        <path class="line" d=${e.path}></path>
      </svg>
    `;
  }
};
le.styles = k`
    :host {
      display: block;
      height: 100%;
      min-height: 0;
      color: var(--savant-success);
      --sparkline-fill-color: var(--savant-success);
      opacity: 1;
    }

    :host([state="warning"]) {
      color: var(--savant-warning);
      --sparkline-fill-color: var(--savant-warning);
    }

    :host([state="caution"]) {
      color: var(--savant-caution);
      --sparkline-fill-color: var(--savant-caution);
    }

    :host([state="muted"]) {
      color: var(--savant-disabled);
      --sparkline-fill-color: var(--savant-disabled);
    }

    svg {
      display: block;
      width: 100%;
      height: 100%;
      min-height: 0;
      color: currentColor;
      overflow: hidden;
    }

    .line {
      fill: none;
      stroke: currentColor;
      stroke-width: 1.45;
      vector-effect: non-scaling-stroke;
      opacity: 0.9;
    }

    .fill-base {
      fill: url("#savant-sparkline-area");
      opacity: 1;
    }

    svg[data-no-history="true"] .line {
      stroke-width: 1.1;
      opacity: 0.82;
      filter: none;
    }
  `;
Me([
  d({ attribute: !1 })
], le.prototype, "points", 2);
Me([
  d({ type: String, reflect: !0 })
], le.prototype, "state", 2);
le = Me([
  C("savant-sparkline")
], le);
function Tt(t) {
  const e = t.map((a) => a.value).filter(Number.isFinite);
  if (!e.length) return;
  if (e.every((a) => Math.max(0, a) === 0)) return zt(e.length);
  if (e.length === 1) {
    const a = Fe(e[0], Ve(e)), o = Math.max(0, e[0]);
    return {
      path: `M 0 ${a} L 100 ${a}`,
      fillPath: o > 0 ? `M 0 ${a} L 100 ${a} L 100 36 L 0 36 Z` : ""
    };
  }
  const s = Ve(e), r = e.map((a, o) => {
    const n = o / (e.length - 1) * 100, l = Math.max(0, a);
    return [n, l === 0 ? D : Fe(a, s), l];
  });
  return {
    path: Rt(r),
    fillPath: It(r)
  };
}
function Fe(t, e) {
  return D - Math.max(0, t) / e * (D - jt);
}
function Ve(t) {
  return Math.max(1, ...t) * 1.25;
}
function Dt() {
  return {
    path: `M 0 ${D} L 100 ${D}`,
    fillPath: ""
  };
}
function zt(t) {
  return t <= 1 ? {
    path: `M 0 ${D} L 100 ${D}`,
    fillPath: ""
  } : { path: Array.from({ length: t }, (s, r) => {
    const i = r / (t - 1) * 100;
    return `${r === 0 ? "M" : "L"} ${i.toFixed(2)} ${D.toFixed(2)}`;
  }).join(" "), fillPath: "" };
}
const jt = 5, D = 33;
function Rt(t) {
  if (t.every(([, , s]) => s === 0))
    return t.map(([s, r], i) => `${i === 0 ? "M" : "L"} ${s.toFixed(2)} ${r.toFixed(2)}`).join(" ");
  const e = [];
  for (let s = 1; s < t.length; s += 1) {
    const r = t[s - 1], i = t[s];
    e.push(`M ${r[0].toFixed(2)} ${r[1].toFixed(2)} L ${i[0].toFixed(2)} ${i[1].toFixed(2)}`);
  }
  return e.join(" ");
}
function It(t) {
  const e = [];
  for (let s = 1; s < t.length; s += 1) {
    const r = t[s - 1], i = t[s];
    r[2] === 0 && i[2] === 0 || e.push(
      [
        `M ${r[0].toFixed(2)} ${r[1].toFixed(2)}`,
        `L ${i[0].toFixed(2)} ${i[1].toFixed(2)}`,
        `L ${i[0].toFixed(2)} 36`,
        `L ${r[0].toFixed(2)} 36`,
        "Z"
      ].join(" ")
    );
  }
  return e.join(" ");
}
var Ft = Object.defineProperty, Vt = Object.getOwnPropertyDescriptor, ye = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? Vt(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && Ft(e, s, i), i;
};
let Y = class extends y {
  constructor() {
    super(...arguments), this.avg = "--", this.max = "--", this.stacked = !1;
  }
  render() {
    return h`
      <div class="metric">
        <span>AVG</span>
        <strong>${this.avg}</strong>
      </div>
      <div class="metric">
        <span>MAX</span>
        <strong>${this.max}</strong>
      </div>
    `;
  }
};
Y.styles = k`
    :host {
      display: flex;
      align-items: end;
      gap: 12px;
      min-width: 0;
    }

    :host([stacked]) {
      width: 100%;
      height: 100%;
      flex-direction: column;
      justify-content: space-between;
      align-items: stretch;
      gap: 0;
    }

    .metric {
      display: grid;
      gap: 3px;
      min-width: 48px;
    }

    :host([stacked]) .metric {
      display: grid;
      grid-template-columns: 36px 44px;
      align-items: baseline;
      justify-content: start;
      gap: 6px;
      min-width: 0;
      width: 100%;
      text-align: center;
    }

    :host([stacked]) span {
      text-align: right;
    }

    :host([stacked]) strong {
      text-align: center;
    }

    :host([stacked]) .metric:first-child {
      order: 2;
    }

    :host([stacked]) .metric:nth-child(2) {
      order: 1;
    }

    span {
      color: var(--savant-muted);
      font-size: 12px;
      font-weight: 400;
      line-height: 1;
      letter-spacing: 0.02em;
    }

    strong {
      color: var(--savant-tile-fg);
      font-size: 15px;
      font-weight: 500;
      line-height: 1.1;
      white-space: nowrap;
      -webkit-text-stroke: 2px var(--savant-text-outline-color);
      paint-order: stroke fill;
    }

  `;
ye([
  d({ type: String })
], Y.prototype, "avg", 2);
ye([
  d({ type: String })
], Y.prototype, "max", 2);
ye([
  d({ type: Boolean, reflect: !0 })
], Y.prototype, "stacked", 2);
Y = ye([
  C("savant-metric-row")
], Y);
function ce(t, e, s) {
  t.dispatchEvent(
    new CustomEvent(e, {
      detail: s,
      bubbles: !0,
      composed: !0
    })
  );
}
var Wt = Object.defineProperty, Ut = Object.getOwnPropertyDescriptor, et = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? Ut(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && Wt(e, s, i), i;
};
const We = {
  flash: "M7,2V13H10V22L17,10H13L17,2H7Z",
  arrow_left: "M20,11H7.83L13.42,5.41L12,4L4,12L12,20L13.41,18.59L7.83,13H20V11Z",
  power: "M13,3H11V13H13V3M17.83,5.17L16.41,6.59C17.99,7.86 19,9.81 19,12A7,7 0 0,1 12,19A7,7 0 0,1 5,12C5,9.81 6.01,7.86 7.59,6.59L6.17,5.17C4.23,6.82 3,9.26 3,12A9,9 0 0,0 12,21A9,9 0 0,0 21,12C21,9.26 19.77,6.82 17.83,5.17Z",
  search: "M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79L20 21.49 21.49 20 15.5 14Zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14Z",
  sort_amount_down: "M3 7h10v2H3V7m0 4h7v2H3v-2m0 4h4v2H3v-2m14-7 4 4h-3v6h-2v-6h-3l4-4Z",
  minimize_2: "",
  layout_dashboard: "M4 3h7v7H4V3m0 11h7v7H4v-7m9-11h7v7h-7V3m0 11h7v7h-7v-7Z"
};
let ve = class extends y {
  constructor() {
    super(...arguments), this.icon = "flash";
  }
  render() {
    return this.icon === "minimize_2" ? se`
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 10h-4v-4" />
          <path d="M20 4l-6 6" />
          <path d="M6 14h4v4" />
          <path d="M10 14l-6 6" />
        </svg>
      ` : h`
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        ${se`<path d=${We[this.icon] ?? We.flash}></path>`}
      </svg>
    `;
  }
};
ve.styles = k`
    :host {
      display: inline-grid;
      place-items: center;
      width: 100%;
      height: 100%;
      line-height: 1;
    }

    svg {
      display: block;
      width: 100%;
      height: 100%;
      fill: currentColor;
    }
  `;
et([
  d({ type: String })
], ve.prototype, "icon", 2);
ve = et([
  C("savant-icon")
], ve);
var Kt = Object.defineProperty, Zt = Object.getOwnPropertyDescriptor, B = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? Zt(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && Kt(e, s, i), i;
};
let M = class extends y {
  constructor() {
    super(...arguments), this.breakerId = "", this.label = "breaker", this.switchState = "off", this.mode = "hold_confirm_off", this.disabled = !1, this.pending = !1, this.holding = !1, this.progress = 0, this.startedAt = 0, this.holdMs = 900, this.cancelHold = () => {
      window.clearTimeout(this.timer), this.holding = !1, this.progress = 0;
    };
  }
  render() {
    const t = this.disabled ? `${this.label} breaker unavailable` : `Hold to ${this.switchState === "on" ? "turn off" : "turn on"} ${this.label} breaker`;
    return h`
      <button
        aria-label=${t}
        title=${t}
        ?disabled=${this.disabled || this.pending}
        class=${this.holding ? "holding" : ""}
        style=${`--progress:${this.progress * 360}deg`}
        @pointerdown=${this.onPointerDown}
        @pointerup=${this.onPointerUp}
        @pointerleave=${this.cancelHold}
        @pointercancel=${this.cancelHold}
        @click=${this.preventClick}
      >
        <span class="icon"><savant-icon icon="power"></savant-icon></span>
      </button>
    `;
  }
  preventClick(t) {
    t.stopPropagation(), t.preventDefault();
  }
  onPointerDown(t) {
    t.stopPropagation(), !(this.disabled || this.pending) && (this.holding = !0, this.startedAt = performance.now(), this.tick());
  }
  onPointerUp(t) {
    t.stopPropagation(), this.holding && (performance.now() - this.startedAt >= this.holdMs && this.requestToggle(), this.cancelHold());
  }
  tick() {
    const t = performance.now() - this.startedAt;
    this.progress = Math.min(1, t / this.holdMs), !(this.progress >= 1) && (this.timer = window.setTimeout(() => this.tick(), 16));
  }
  requestToggle() {
    ce(this, "savant-breaker-toggle", { breakerId: this.breakerId });
  }
};
M.styles = k`
    :host {
      display: inline-grid;
      place-items: center;
    }

    button {
      width: 46px;
      height: 46px;
      padding: 0;
      border-radius: 999px;
      border: 2px solid currentColor;
      background:
        conic-gradient(currentColor var(--progress, 0deg), transparent 0),
        var(--savant-tile-bg);
      color: var(--control-color, var(--savant-success));
      display: grid;
      place-items: center;
      cursor: pointer;
      touch-action: none;
      box-shadow: var(--savant-shadow-sm);
    }

    :host-context(savant-breaker-tile[stacked]) button {
      width: 44px;
      height: 44px;
    }

    button[disabled] {
      cursor: default;
      color: var(--savant-disabled);
      box-shadow: none;
      opacity: 0.7;
    }

    .icon {
      width: 34px;
      height: 34px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background: var(--savant-card-bg);
      line-height: 1;
    }

    savant-icon {
      display: block;
      width: 20px;
      height: 20px;
    }
  `;
B([
  d({ type: String })
], M.prototype, "breakerId", 2);
B([
  d({ type: String })
], M.prototype, "label", 2);
B([
  d({ type: String })
], M.prototype, "switchState", 2);
B([
  d({ type: String })
], M.prototype, "mode", 2);
B([
  d({ type: Boolean })
], M.prototype, "disabled", 2);
B([
  d({ type: Boolean })
], M.prototype, "pending", 2);
B([
  g()
], M.prototype, "holding", 2);
B([
  g()
], M.prototype, "progress", 2);
M = B([
  C("savant-hold-control-button")
], M);
function z(t) {
  const e = typeof t == "number" ? t : Number(t);
  return Number.isFinite(e) ? e : void 0;
}
function re(t) {
  if (t === void 0 || !Number.isFinite(t)) return "--";
  const e = Math.abs(t);
  return e >= 1e3 ? `${qt(t / 1e3, e >= 1e4 ? 1 : 2)} kW` : `${Math.round(t)} W`;
}
function qt(t, e) {
  return t.toLocaleString(void 0, {
    maximumFractionDigits: e,
    minimumFractionDigits: 0
  });
}
function Gt(t, e = "kWh") {
  return t === void 0 || !Number.isFinite(t) ? "--" : `${t.toLocaleString(void 0, { maximumFractionDigits: 2 })} ${e}`;
}
var Qt = Object.defineProperty, Yt = Object.getOwnPropertyDescriptor, P = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? Yt(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && Qt(e, s, i), i;
};
let $ = class extends y {
  constructor() {
    super(...arguments), this.highLoadThresholdWatts = 2e3, this.warningLoadThresholdWatts = 1e3, this.graphLoading = !1, this.pending = !1, this.stacked = !1, this.mobileLayout = "standard", this.error = "";
  }
  render() {
    var c, u, p, m, _, S, A;
    const t = this.runtimeState(), e = this.visualState(t.powerWatts, t.switchState, t.available), s = this.loadState(t.powerWatts), r = this.stacked && this.mobileLayout === "ultra_compact", i = this.display.show_area ? this.breaker.areaName : void 0, a = e === "off" ? Jt((c = this.statistics) == null ? void 0 : c.points.length) : ((u = this.statistics) == null ? void 0 : u.points) ?? [], o = !!((p = this.statistics) != null && p.points.length), n = !r && o && (((m = this.statistics) == null ? void 0 : m.averageWatts) !== void 0 || ((_ = this.statistics) == null ? void 0 : _.maximumWatts) !== void 0), l = this.display.show_controls && this.display.control_mode !== "hidden" && this.breaker.controllable && !!this.breaker.entities.switch;
    return h`
      <button class=${`tile ${e} ${this.pending ? "pending" : ""} ${r ? "ultra-compact" : ""}`} @click=${this.openMoreInfo}>
        <span class="mobile-bar" aria-hidden="true"></span>
        <span class="topline">
          <span class="state-dot" aria-hidden="true"></span>
          ${this.display.show_state ? h`<span class="state-text">${Xt(e, t.switchState)}</span>` : ""}
          ${this.display.show_icon ? this.renderEntityIcon() : ""}
        </span>
        <span class="name">${this.display.label}</span>
        ${i && !r ? h`<span class="subtitle">${i}</span>` : ""}
        <span class="power">${this.display.show_current_power ? re(t.powerWatts) : ""}</span>
        <span class="graph">
          ${this.graphLoading && e !== "off" ? this.renderGraphSkeleton() : this.display.show_sparkline ? h`<savant-sparkline
                  .points=${a}
                  .state=${!o || e === "unavailable" || e === "off" ? "muted" : s === "high" ? "warning" : s === "warning" ? "caution" : "normal"}
                ></savant-sparkline>` : ""}
        </span>
        <span class="metrics">
          ${n && (this.display.show_average_power || this.display.show_maximum_power) ? h`<savant-metric-row
                .avg=${this.display.show_average_power ? re((S = this.statistics) == null ? void 0 : S.averageWatts) : "--"}
                .max=${this.display.show_maximum_power ? re((A = this.statistics) == null ? void 0 : A.maximumWatts) : "--"}
                ?stacked=${this.stacked}
              ></savant-metric-row>` : ""}
          ${this.display.show_energy ? h`<span class="energy">${Gt(t.energyValue)}</span>` : ""}
        </span>
        ${this.error ? h`<span class="feedback">${this.error}</span>` : ""}
        ${l ? h`<savant-hold-control-button
              class="control"
              .breakerId=${this.breaker.id}
              .label=${this.display.label}
              .mode=${this.display.control_mode === "hold" ? "hold" : "hold_confirm_off"}
              .switchState=${t.switchState ?? "off"}
              .pending=${this.pending}
              ?disabled=${!t.available}
            ></savant-hold-control-button>` : ""}
      </button>
    `;
  }
  renderEntityIcon() {
    var s, r;
    const t = this.breaker.entities.power, e = t ? (r = (s = this.hass) == null ? void 0 : s.states[t]) == null ? void 0 : r.attributes.icon : void 0;
    return typeof e == "string" && e && customElements.get("ha-icon") ? h`<ha-icon class="entity-icon" .icon=${e}></ha-icon>` : h`<savant-icon class="entity-icon" icon="flash"></savant-icon>`;
  }
  renderGraphSkeleton() {
    return h`
      <span class="graph-skeleton" aria-hidden="true">
        <svg viewBox="0 0 100 36" preserveAspectRatio="none">
          <path class="graph-skeleton-fill" d="M 0 28 L 12 22 L 26 20 L 42 25 L 56 27 L 68 17 L 82 14 L 100 18 L 100 36 L 0 36 Z"></path>
          <path class="graph-skeleton-line" d="M 0 28 L 12 22 L 26 20 L 42 25 L 56 27 L 68 17 L 82 14 L 100 18"></path>
        </svg>
      </span>
    `;
  }
  runtimeState() {
    var n, l, c, u, p, m, _, S, A, L;
    const t = this.breaker.entities.power, e = this.breaker.entities.energy, s = this.breaker.entities.switch, r = t ? z((l = (n = this.hass) == null ? void 0 : n.states[t]) == null ? void 0 : l.state) : void 0, i = e ? z((u = (c = this.hass) == null ? void 0 : c.states[e]) == null ? void 0 : u.state) : void 0, a = this.optimisticSwitchState ?? (s ? (m = (p = this.hass) == null ? void 0 : p.states[s]) == null ? void 0 : m.state : void 0), o = this.breaker.available && (!t || ((S = (_ = this.hass) == null ? void 0 : _.states[t]) == null ? void 0 : S.state) !== "unavailable") && (!s || ((L = (A = this.hass) == null ? void 0 : A.states[s]) == null ? void 0 : L.state) !== "unavailable");
    return { powerWatts: r, energyValue: i, switchState: a, available: o };
  }
  visualState(t, e, s = !0) {
    return this.error ? "error" : this.pending ? "pending" : s ? e === "off" ? "off" : e === "on" ? "on" : t === 0 ? "off" : "on" : "unavailable";
  }
  loadState(t) {
    return t !== void 0 && t > this.highLoadThresholdWatts ? "high" : t !== void 0 && t > this.warningLoadThresholdWatts ? "warning" : "normal";
  }
  openMoreInfo(t) {
    if (t.target.closest("savant-hold-control-button")) return;
    const s = this.breaker.entities.power ?? this.breaker.entities.switch ?? this.breaker.entities.energy;
    s && ce(this, "hass-action", {
      config: {
        entity: s,
        tap_action: { action: "more-info" }
      },
      action: "tap"
    });
  }
};
$.styles = k`
    :host {
      display: block;
      min-width: 0;
      aspect-ratio: 1 / 1;
      --status-color: var(--savant-success);
      --control-color: var(--status-color);
      --savant-text-halo:
        0 0 2px var(--savant-tile-bg),
        0 1px 1px var(--savant-tile-bg),
        1px 0 1px var(--savant-tile-bg),
        0 -1px 1px var(--savant-tile-bg),
        -1px 0 1px var(--savant-tile-bg);
      --savant-text-outline-color: var(--savant-tile-bg);
      --savant-font-family:
        Inter, "SF Pro Display", "SF Pro Text", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    .tile {
      position: relative;
      display: grid;
      grid-template-rows: auto auto auto 1fr auto;
      width: 100%;
      height: 100%;
      min-height: 0;
      padding: 16px;
      overflow: hidden;
      text-align: left;
      border: 1px solid var(--savant-border);
      border-radius: var(--savant-radius);
      background:
        linear-gradient(
          180deg,
          color-mix(in srgb, var(--savant-tile-bg-strong) 60%, var(--savant-surface-tint)),
          var(--savant-tile-bg)
        );
      color: var(--savant-tile-fg);
      box-shadow: var(--savant-shadow-sm);
      font-family: var(--savant-breaker-font-family, var(--savant-font-family));
      font-weight: 400;
      cursor: pointer;
    }

    .tile.off,
    .tile.unavailable {
      --status-color: var(--savant-disabled);
    }

    .tile.off {
      --status-color: var(--savant-error);
    }

    .tile.error {
      --status-color: var(--savant-error);
    }

    .topline {
      display: flex;
      align-items: center;
      gap: 7px;
      min-width: 0;
      color: var(--status-color);
      font-size: 12px;
      line-height: 1.2;
      font-weight: 500;
      text-transform: uppercase;
      position: relative;
      z-index: 1;
    }

    .state-dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--status-color);
      flex: none;
    }

    .entity-icon {
      margin-left: auto;
      width: 24px;
      height: 24px;
      color: color-mix(in srgb, var(--primary-text-color) 86%, var(--secondary-text-color));
      font-size: 24px;
      line-height: 1;
    }

    .name {
      display: block;
      margin-top: 5px;
      font-size: 15px;
      font-weight: 500;
      line-height: 1.22;
      min-height: 1.22em;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      position: relative;
      z-index: 1;
      text-shadow: var(--savant-text-halo);
      -webkit-text-stroke: 4px var(--savant-text-outline-color);
      paint-order: stroke fill;
    }

    .subtitle {
      color: var(--savant-muted);
      font-size: 12px;
      line-height: 1.25;
      font-weight: 400;
      min-height: 1.25em;
      margin-top: 1px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      position: relative;
      z-index: 1;
      -webkit-text-stroke: 3px var(--savant-text-outline-color);
      paint-order: stroke fill;
    }

    .power {
      margin-top: 11px;
      font-size: 28px;
      font-weight: 500;
      color: var(--status-color);
      letter-spacing: 0;
      line-height: 1.12;
      white-space: nowrap;
      position: relative;
      z-index: 1;
      text-shadow: var(--savant-text-halo);
      -webkit-text-stroke: 4px var(--savant-text-outline-color);
      paint-order: stroke fill;
    }

    :host(:not([stacked])) .subtitle {
      position: absolute;
      left: 16px;
      right: 16px;
      top: 68px;
      margin: 0;
      min-height: 0;
    }

    :host(:not([stacked])) .power {
      position: absolute;
      left: 16px;
      right: 16px;
      top: 86px;
      margin: 0;
    }

    .tile.on .power {
      color: var(--savant-tile-fg);
    }

    .graph {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 58px;
      top: 110px;
      height: auto;
      min-height: 0;
      margin: 0;
      pointer-events: none;
      z-index: 0;
    }

    .metrics {
      position: absolute;
      left: 16px;
      right: 74px;
      bottom: 14px;
      display: flex;
      align-items: end;
      gap: 10px;
      min-width: 0;
      z-index: 2;
    }

    .energy,
    .feedback {
      color: var(--savant-muted);
      font-size: 12px;
    }

    .feedback {
      position: absolute;
      left: 16px;
      bottom: 58px;
      color: var(--savant-error);
    }

    .control {
      position: absolute;
      right: 14px;
      bottom: 14px;
      z-index: 3;
      --control-color: var(--status-color);
    }

    .mobile-bar {
      display: none;
    }

    .graph-skeleton {
      display: block;
      width: 100%;
      height: 100%;
      min-height: 32px;
      color: var(--status-color);
      opacity: 0.62;
    }

    .graph-skeleton svg {
      display: block;
      width: 100%;
      height: 100%;
      min-height: 32px;
    }

    .graph-skeleton-fill {
      fill: currentColor;
      opacity: 0.18;
    }

    .graph-skeleton-line {
      fill: none;
      stroke: currentColor;
      vector-effect: non-scaling-stroke;
    }

    .graph-skeleton-line {
      stroke-width: 1.45;
      opacity: 0.72;
    }

    :host-context([density="compact"]) .tile {
      padding: 12px;
    }

    :host-context([density="compact"]) .power {
      margin-top: 8px;
      font-size: 25px;
    }

    :host-context([density="compact"]) .graph {
      top: 98px;
      height: auto;
      min-height: 0;
      bottom: 52px;
    }

    :host([stacked]) {
      aspect-ratio: auto;
    }

    :host([stacked]) .tile {
      min-height: 128px;
      height: auto;
      display: block;
      padding: 12px 142px 12px 32px;
    }

    :host([stacked]) .mobile-bar {
      display: block;
      position: absolute;
      top: 10px;
      bottom: 10px;
      left: 8px;
      width: 7px;
      border-radius: 999px;
      background: var(--status-color);
    }

    :host([stacked]) .tile.unavailable .mobile-bar {
      background: repeating-linear-gradient(
        to bottom,
        var(--status-color) 0 12px,
        transparent 12px 19px
      );
    }

    :host([stacked]) .topline {
      display: contents;
      gap: 0;
    }

    :host([stacked]) .state-dot {
      display: none;
    }

    :host([stacked]) .state-text {
      display: none;
    }

    :host([stacked]) .name {
      position: absolute;
      top: 14px;
      left: 58px;
      right: 136px;
      margin: 0;
      font-size: 16px;
      line-height: 1.15;
      min-height: 0;
    }

    :host([stacked]) .subtitle {
      position: absolute;
      top: 32px;
      left: 58px;
      right: 136px;
      margin: 0;
      min-height: 0;
      font-size: 12px;
      line-height: 1.15;
    }

    :host([stacked]) .power {
      position: absolute;
      top: 50px;
      left: 32px;
      right: 136px;
      margin: 0;
      font-size: 27px;
      line-height: 1;
      z-index: 2;
    }

    :host([stacked]) .graph {
      position: absolute;
      left: 32px;
      right: 124px;
      top: auto;
      bottom: 12px;
      height: 68px;
      min-height: 68px;
      margin: 0;
    }

    :host([stacked]) .metrics {
      left: auto;
      right: 21px;
      top: 12px;
      bottom: 12px;
      width: 86px;
      justify-content: center;
      align-items: stretch;
    }

    :host([stacked]) .control {
      right: 21px;
      top: 50%;
      bottom: auto;
      transform: translateY(-50%);
    }

    :host([stacked]) .entity-icon {
      position: absolute;
      left: 32px;
      top: 13px;
      width: 20px;
      height: 20px;
      font-size: 20px;
    }

    :host([stacked][mobile-layout="ultra_compact"]) .tile {
      min-height: 44px;
      padding: 7px 82px 7px 18px;
    }

    :host([stacked][mobile-layout="ultra_compact"]) .mobile-bar {
      top: 8px;
      bottom: 8px;
      left: 6px;
      width: 5px;
    }

    :host([stacked][mobile-layout="ultra_compact"]) .name {
      top: 50%;
      left: 18px;
      right: 150px;
      transform: translateY(-50%);
      font-size: 14px;
      line-height: 1.1;
      z-index: 2;
    }

    :host([stacked][mobile-layout="ultra_compact"]) .power {
      top: 50%;
      left: auto;
      right: 74px;
      width: 70px;
      transform: translateY(-50%);
      font-size: 18px;
      text-align: right;
      color: var(--savant-tile-fg);
      z-index: 2;
    }

    :host([stacked][mobile-layout="ultra_compact"]) .graph,
    :host([stacked][mobile-layout="ultra_compact"]) .metrics,
    :host([stacked][mobile-layout="ultra_compact"]) .entity-icon,
    :host([stacked][mobile-layout="ultra_compact"]) .subtitle {
      display: none;
    }

    :host([stacked][mobile-layout="ultra_compact"]) .graph {
      display: block;
      position: absolute;
      top: 50%;
      left: 64px;
      right: 146px;
      width: auto;
      height: 28px;
      min-height: 28px;
      transform: translateY(-50%);
      z-index: 0;
    }

    :host([stacked][mobile-layout="ultra_compact"]) savant-sparkline,
    :host([stacked][mobile-layout="ultra_compact"]) .graph-skeleton {
      height: 28px;
      min-height: 28px;
      max-height: 28px;
      opacity: 0.95;
    }

    :host([stacked][mobile-layout="ultra_compact"]) .control {
      right: 10px;
      transform: translateY(-50%) scale(0.76);
      transform-origin: right center;
    }

    :host([stacked][mobile-layout="ultra_compact"]) .feedback {
      left: 18px;
      right: 84px;
      bottom: 3px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  `;
P([
  d({ attribute: !1 })
], $.prototype, "hass", 2);
P([
  d({ attribute: !1 })
], $.prototype, "breaker", 2);
P([
  d({ attribute: !1 })
], $.prototype, "display", 2);
P([
  d({ attribute: !1 })
], $.prototype, "statistics", 2);
P([
  d({ type: Number })
], $.prototype, "highLoadThresholdWatts", 2);
P([
  d({ type: Number })
], $.prototype, "warningLoadThresholdWatts", 2);
P([
  d({ type: Boolean })
], $.prototype, "graphLoading", 2);
P([
  d({ type: Boolean })
], $.prototype, "pending", 2);
P([
  d({ type: Boolean, reflect: !0 })
], $.prototype, "stacked", 2);
P([
  d({ type: String, attribute: "mobile-layout", reflect: !0 })
], $.prototype, "mobileLayout", 2);
P([
  d({ type: String })
], $.prototype, "optimisticSwitchState", 2);
P([
  d({ type: String })
], $.prototype, "error", 2);
$ = P([
  C("savant-breaker-tile")
], $);
function Xt(t, e) {
  return t === "unavailable" ? "Unavailable" : e === "off" || t === "off" ? "Off" : "On";
}
function Jt(t = 2) {
  return Array.from({ length: Math.max(2, t) }, (e, s) => ({
    start: s,
    value: 0
  }));
}
const es = k`
  .skeleton {
    position: relative;
    overflow: hidden;
    background: color-mix(in srgb, var(--savant-muted) 16%, transparent);
    border-radius: 999px;
  }

  .skeleton::after {
    content: "";
    position: absolute;
    inset: 0;
    transform: translateX(-100%);
    background: linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--primary-text-color) 16%, transparent),
      transparent
    );
    animation: savant-shimmer 1.35s infinite;
  }

  @media (prefers-reduced-motion: reduce) {
    .skeleton::after {
      animation: none;
    }
  }

  @keyframes savant-shimmer {
    to {
      transform: translateX(100%);
    }
  }
`;
var ts = Object.defineProperty, ss = Object.getOwnPropertyDescriptor, tt = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? ss(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && ts(e, s, i), i;
};
let me = class extends y {
  constructor() {
    super(...arguments), this.stacked = !1;
  }
  render() {
    return h`
      <div class="bar skeleton"></div>
      <div class="status skeleton"></div>
      <div class="title skeleton"></div>
      <div class="subtitle skeleton"></div>
      <div class="power skeleton"></div>
      <div class="graph" aria-hidden="true">
        <svg viewBox="0 0 100 36" preserveAspectRatio="none">
          <path class="graph-fill" d="M 0 28 L 12 22 L 26 20 L 42 25 L 56 27 L 68 17 L 82 14 L 100 18 L 100 36 L 0 36 Z"></path>
          <path class="graph-line" d="M 0 28 L 12 22 L 26 20 L 42 25 L 56 27 L 68 17 L 82 14 L 100 18"></path>
        </svg>
      </div>
      <div class="avg skeleton"></div>
      <div class="max skeleton"></div>
      <div class="control skeleton"></div>
    `;
  }
};
me.styles = [
  es,
  k`
      :host {
        position: relative;
        display: grid;
        aspect-ratio: 1 / 1;
        min-height: 0;
        padding: 16px;
        border-radius: var(--savant-radius);
        background: var(--savant-tile-bg);
        box-shadow: var(--savant-shadow-sm);
      }

      .status {
        width: 54px;
        height: 12px;
      }

      .title {
        width: 68%;
        height: 18px;
        margin-top: 16px;
      }

      .subtitle {
        width: 45%;
        height: 14px;
        margin-top: 8px;
      }

      .power {
        width: 44%;
        height: 34px;
        margin-top: 22px;
      }

      .graph {
        width: 100%;
        height: 38px;
        margin-top: 10px;
        border-radius: 0;
        opacity: 0.72;
      }

      svg {
        display: block;
        width: 100%;
        height: 100%;
      }

      .graph-fill {
        fill: color-mix(in srgb, var(--savant-success) 20%, transparent);
      }

      .graph-line {
        fill: none;
        stroke: color-mix(in srgb, var(--savant-success) 58%, var(--savant-muted));
        stroke-width: 1.45;
        vector-effect: non-scaling-stroke;
      }

      .avg,
      .max {
        position: absolute;
        bottom: 18px;
        width: 48px;
        height: 28px;
        overflow: visible;
        background: transparent;
        border-radius: 0;
      }

      .avg {
        left: 16px;
      }

      .max {
        left: 80px;
      }

      .avg::before,
      .max::before,
      .avg::after,
      .max::after {
        content: "";
        position: absolute;
        left: 0;
        transform: none;
        animation: none;
        border-radius: 999px;
        background:
          linear-gradient(
            90deg,
            transparent,
            color-mix(in srgb, var(--primary-text-color) 16%, transparent),
            transparent
          ),
          color-mix(in srgb, var(--savant-muted) 16%, transparent);
        background-size: 200% 100%, auto;
      }

      .avg::before,
      .max::before {
        top: 0;
        width: 24px;
        height: 9px;
      }

      .avg::after,
      .max::after {
        bottom: 0;
        width: 44px;
        height: 13px;
      }

      .control {
        position: absolute;
        right: 16px;
        bottom: 16px;
        width: 46px;
        height: 46px;
        border-radius: 50%;
      }

      .bar {
        display: none;
      }

      :host([stacked]) {
        aspect-ratio: auto;
        min-height: 128px;
        padding: 12px 142px 12px 32px;
      }

      :host([stacked]) .bar {
        display: block;
        position: absolute;
        left: 10px;
        top: 14px;
        bottom: 14px;
        width: 8px;
      }

      :host([stacked]) .status {
        position: absolute;
        left: 32px;
        top: 13px;
        width: 20px;
        height: 20px;
      }

      :host([stacked]) .title {
        position: absolute;
        left: 58px;
        right: 136px;
        top: 13px;
        width: auto;
        margin: 0;
      }

      :host([stacked]) .subtitle {
        position: absolute;
        left: 58px;
        right: 136px;
        top: 31px;
        width: auto;
        margin: 0;
      }

      :host([stacked]) .power {
        position: absolute;
        left: 32px;
        right: 136px;
        top: 45px;
        width: auto;
        max-width: 104px;
        margin: 0;
      }

      :host([stacked]) .graph {
        position: absolute;
        left: 32px;
        right: 136px;
        bottom: 12px;
        width: auto;
        height: 30px;
        margin: 0;
      }

      :host([stacked]) .avg,
      :host([stacked]) .max {
        right: 21px;
        left: auto;
        width: 86px;
        height: 12px;
      }

      :host([stacked]) .avg::before,
      :host([stacked]) .max::before {
        top: 2px;
        left: 0;
        width: 34px;
        height: 8px;
      }

      :host([stacked]) .avg::after,
      :host([stacked]) .max::after {
        top: 0;
        right: 0;
        left: auto;
        width: 46px;
        height: 12px;
      }

      :host([stacked]) .avg {
        bottom: 22px;
      }

      :host([stacked]) .max {
        top: 22px;
      }

      :host([stacked]) .control {
        right: 21px;
        top: 42px;
        bottom: auto;
      }
    `
];
tt([
  d({ type: Boolean, reflect: !0 })
], me.prototype, "stacked", 2);
me = tt([
  C("savant-breaker-tile-skeleton")
], me);
var rs = Object.getOwnPropertyDescriptor, is = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? rs(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = o(i) || i);
  return i;
};
let ke = class extends y {
  render() {
    return h`
      <div class="empty">
        <strong>No Savant breaker entities discovered.</strong>
        <span>Open the card editor to add manual mappings or check Savant Energy entity metadata.</span>
      </div>
    `;
  }
};
ke.styles = k`
    .empty {
      display: grid;
      gap: 6px;
      padding: 22px;
      border-radius: var(--savant-radius);
      background: color-mix(in srgb, var(--secondary-text-color) 10%, transparent);
      color: var(--primary-text-color);
    }

    span {
      color: var(--secondary-text-color);
    }
  `;
ke = is([
  C("savant-board-empty-state")
], ke);
var as = Object.defineProperty, os = Object.getOwnPropertyDescriptor, st = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? os(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && as(e, s, i), i;
};
let fe = class extends y {
  constructor() {
    super(...arguments), this.message = "Unable to load breaker board.";
  }
  render() {
    return h`<div class="error">${this.message}</div>`;
  }
};
fe.styles = k`
    .error {
      padding: 16px;
      border-radius: var(--savant-radius);
      color: var(--error-color);
      background: color-mix(in srgb, var(--error-color) 12%, transparent);
    }
  `;
st([
  d({ type: String })
], fe.prototype, "message", 2);
fe = st([
  C("savant-board-error-state")
], fe);
var ns = Object.defineProperty, ls = Object.getOwnPropertyDescriptor, Ee = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? ls(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && ns(e, s, i), i;
};
let he = class extends y {
  render() {
    var e;
    const t = (e = this.breaker) == null ? void 0 : e.semMetrics;
    return !this.breaker || !t ? v : h`
      <article class="sem-chip">
        <div class="node top">${this.metric("Solar", "flash", t.solar)}</div>
        <div class="node left">${this.metric("Battery", "power", t.batteryPower)}</div>
        <div class="node center">${this.metric("Home Load", "power", t.homeLoad)}</div>
        <div class="node right">${this.metric("Grid", "flash", t.grid)}</div>
        <div class="node bottom">
          ${t.batterySoc ? this.percentMetric("Battery SoC", "power", t.batterySoc) : v}
        </div>
      </article>
    `;
  }
  metric(t, e, s) {
    var i, a;
    const r = s ? z((a = (i = this.hass) == null ? void 0 : i.states[s]) == null ? void 0 : a.state) : void 0;
    return h`<div class="metric"><savant-icon .icon=${e}></savant-icon><span>${t}</span><strong>${re(r)}</strong></div>`;
  }
  percentMetric(t, e, s) {
    var i, a;
    const r = z((a = (i = this.hass) == null ? void 0 : i.states[s]) == null ? void 0 : a.state);
    return h`<div class="metric"><savant-icon .icon=${e}></savant-icon><span>${t}</span><strong>${r === void 0 ? "--" : `${Math.round(r)}%`}</strong></div>`;
  }
};
he.styles = k`
    .sem-chip {
      position: relative;
      min-height: 170px;
      padding: 12px;
      border: 1px solid var(--savant-border);
      border-radius: var(--savant-radius);
      background: var(--savant-tile-bg);
      box-shadow: var(--savant-shadow-sm);
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      grid-template-rows: auto auto auto;
      gap: 8px;
      grid-column: 1 / -1;
    }
    .sem-chip::before,
    .sem-chip::after {
      content: "";
      position: absolute;
      pointer-events: none;
      background: color-mix(in srgb, var(--primary-text-color) 18%, transparent);
    }
    .sem-chip::before { left: 50%; top: 42px; width: 1px; height: 84px; transform: translateX(-0.5px); }
    .sem-chip::after { left: 22%; right: 22%; top: 84px; height: 1px; }
    .node.top { grid-column: 2; grid-row: 1; }
    .node.left { grid-column: 1; grid-row: 2; }
    .node.center { grid-column: 2; grid-row: 2; }
    .node.right { grid-column: 3; grid-row: 2; }
    .node.bottom { grid-column: 2; grid-row: 3; }
    .metric {
      position: relative;
      z-index: 1;
      display: grid;
      justify-items: center;
      gap: 2px;
      text-align: center;
      padding: 6px;
      border-radius: 10px;
      background: color-mix(in srgb, var(--savant-card-bg) 88%, var(--savant-app-bg));
    }
    .metric savant-icon { width: 14px; height: 14px; }
    .metric span { font-size: 11px; color: var(--secondary-text-color); }
    .metric strong { font-size: 13px; font-weight: 700; color: var(--primary-text-color); }
  `;
Ee([
  d({ attribute: !1 })
], he.prototype, "hass", 2);
Ee([
  d({ attribute: !1 })
], he.prototype, "breaker", 2);
he = Ee([
  C("savant-sem-chip")
], he);
class U {
  constructor(e) {
    this.hass = e;
  }
  async fetchScenes() {
    const e = await this.hass.callApi("GET", "savant_energy/scenes");
    return e != null && e.scenes ? e.scenes.map((s) => ({ id: s.scene_id, name: s.name })) : [];
  }
  async fetchSceneBreakers(e) {
    const s = await this.hass.callApi("GET", `savant_energy/scene_breakers/${e}`);
    return s != null && s.breakers && typeof s.breakers == "object" ? { ...s.breakers } : {};
  }
  async createScene(e, s) {
    await this.hass.callApi("POST", "savant_energy/scenes", { name: e, relay_states: s });
  }
  async updateScene(e, s, r) {
    await this.hass.callApi("POST", `savant_energy/scenes/${e}`, { name: s, relay_states: r });
  }
  async deleteScene(e) {
    await this.hass.callApi("DELETE", `savant_energy/scenes/${e}`);
  }
}
const rt = 168;
function cs(t, e) {
  const s = t == null ? void 0 : t.averageWatts;
  if (s === void 0 || !Number.isFinite(s))
    return {};
  const r = s / 1e3, i = r * rt, a = {
    averageWatts: s,
    averageKwPerHour: r,
    estimatedWeeklyKwh: i
  };
  return e && e > 0 && (a.batteryDrainPercentPerHour = r / e * 100), a;
}
function hs(t, e, s) {
  const r = Object.keys(t), i = r.length;
  let a = 0, o = 0;
  for (const u of r) {
    if (!t[u]) continue;
    a++;
    const p = e.get(u);
    p != null && p.averageWatts && Number.isFinite(p.averageWatts) && (o += p.averageWatts);
  }
  const n = o / 1e3, l = n * rt, c = {
    totalOnBreakers: a,
    totalBreakers: i,
    totalAverageWatts: o,
    totalKwhPerHour: n,
    totalWeeklyKwh: l
  };
  return s && s > 0 && (c.batteryDrainPercentPerHour = n / s * 100), c;
}
function it(t) {
  return t === void 0 || !Number.isFinite(t) ? "--" : t >= 10 ? `${t.toFixed(1)} kWh` : t >= 1 ? `${t.toFixed(2)} kWh` : `${(t * 1e3).toFixed(0)} Wh`;
}
function at(t) {
  return t === void 0 || !Number.isFinite(t) ? "" : `${t.toFixed(1)}%/h`;
}
const ot = k`
  :host {
    display: block;
    color: var(--primary-text-color);
    --savant-card-bg: var(--ha-card-background, var(--card-background-color, #ffffff));
    --savant-app-bg: var(--primary-background-color, #f4f6f8);
    --savant-tile-bg: color-mix(in srgb, var(--savant-card-bg) 96%, white);
    --savant-tile-bg-strong: color-mix(in srgb, var(--savant-card-bg) 91%, white);
    --savant-surface-tint: color-mix(in srgb, var(--primary-color, #4caf50) 4%, transparent);
    --savant-tile-fg: var(--primary-text-color, #1d2327);
    --savant-muted: var(--secondary-text-color, #a9b0b4);
    --savant-success: var(--success-color, #7acb54);
    --savant-caution: var(--savant-caution-color, #f5cc4d);
    --savant-warning: var(--warning-color, #ff8f22);
    --savant-error: var(--error-color, #f05246);
    --savant-disabled: var(--disabled-text-color, #8d9499);
    --savant-border: color-mix(in srgb, var(--divider-color, #6f767b) 30%, transparent);
    --savant-border-strong: color-mix(in srgb, var(--divider-color, #6f767b) 44%, transparent);
    --savant-shadow-sm: 0 8px 18px rgb(15 23 42 / 0.08);
    --savant-shadow-md: 0 12px 28px rgb(15 23 42 / 0.1);
    --savant-radius: var(--savant-breaker-radius, 12px);
    font-family: var(--paper-font-body1_-_font-family, inherit);
  }

  ha-card {
    overflow: visible;
    padding: 16px;
    background: var(--savant-card-bg);
  }

  .board-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 14px;
  }

  .board-title {
    margin: 0;
    font-size: 20px;
    font-weight: 650;
    letter-spacing: 0;
  }

  .board-grid {
    container-type: inline-size;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(var(--tile-min-width, 262px), 1fr));
    align-items: start;
    gap: var(--tile-gap, 12px);
  }

  :host([density="compact"]) .board-grid {
    --tile-min-width: 224px;
    --tile-gap: 10px;
  }

  .board-grid.stacked {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .group-title {
    grid-column: 1 / -1;
    margin: 8px 0 0;
    color: var(--secondary-text-color);
    font-size: 13px;
    font-weight: 650;
    text-transform: uppercase;
  }
`;
var ds = Object.defineProperty, ps = Object.getOwnPropertyDescriptor, j = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? ps(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && ds(e, s, i), i;
};
let E = class extends y {
  constructor() {
    super(...arguments), this.name = "", this.entityId = "", this.isOn = !1, this.loading = !1, this.controllable = !0;
  }
  handleClick() {
    this.controllable && ce(this, "savant-scene-toggle", {
      entityId: this.entityId,
      newState: !this.isOn
    });
  }
  render() {
    const t = this.isOn && this.averageWatts !== void 0 ? cs(
      { averageWatts: this.averageWatts },
      this.batteryCapacityKwh
    ) : void 0;
    return h`
      <button
        class="row ${this.isOn ? "on" : "off"}${this.controllable ? "" : " locked"}"
        ?disabled=${!this.controllable}
        @click=${this.handleClick}
      >
        <span class="status-bar" aria-hidden="true"></span>
        <span class="body">
          <span class="header">
            <span class="name">${this.name}</span>
            <span class="badge ${this.isOn ? "on" : "off"}">${this.isOn ? "ON" : "OFF"}</span>
          </span>
          ${this.renderStats(t)}
        </span>
        ${this.controllable ? "" : this.renderLockIcon()}
      </button>
    `;
  }
  renderStats(t) {
    if (!this.isOn) return "";
    if (this.loading)
      return h`<span class="stats"><span class="stats-line muted">Loading…</span></span>`;
    if (this.averageWatts === void 0)
      return h`<span class="stats"><span class="stats-line muted">No data</span></span>`;
    const e = [], s = t == null ? void 0 : t.averageKwPerHour, r = t == null ? void 0 : t.batteryDrainPercentPerHour;
    return s !== void 0 && e.push(`${it(s)}/h`), r !== void 0 && e.push(at(r)), h`
      <span class="stats">
        <span class="stats-line">${e.join("  ·  ")}</span>
      </span>
    `;
  }
  renderLockIcon() {
    return h`
      <span class="lock-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path
            d="M18,8H17V6A5,5 0 0,0 12,1A5,5 0 0,0 7,6V8H6A2,2 0 0,0 4,10V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V10A2,2 0 0,0 18,8M12,17A2,2 0 0,1 10,15A2,2 0 0,1 12,13A2,2 0 0,1 14,15A2,2 0 0,1 12,17M15.1,8H8.9V6A3.1,3.1 0 0,1 12,2.9A3.1,3.1 0 0,1 15.1,6V8Z"
          />
        </svg>
      </span>
    `;
  }
};
E.styles = k`
    :host {
      display: block;
      --status-color: var(--savant-success);
      --savant-text-halo:
        0 0 2px var(--savant-tile-bg),
        0 1px 1px var(--savant-tile-bg),
        1px 0 1px var(--savant-tile-bg),
        0 -1px 1px var(--savant-tile-bg),
        -1px 0 1px var(--savant-tile-bg);
      --savant-text-outline-color: var(--savant-tile-bg);
    }

    .row {
      display: flex;
      align-items: stretch;
      width: 100%;
      min-width: 0;
      padding: 8px 14px;
      text-align: left;
      border: 1px solid var(--savant-border);
      border-radius: var(--savant-radius);
      background:
        linear-gradient(
          180deg,
          color-mix(in srgb, var(--savant-tile-bg-strong) 60%, var(--savant-surface-tint)),
          var(--savant-tile-bg)
        );
      box-shadow: var(--savant-shadow-sm);
      color: var(--savant-tile-fg);
      font-family: var(--savant-font-family, Inter, "SF Pro Display", "SF Pro Text", Roboto, "Helvetica Neue", Arial, sans-serif);
      font-weight: 400;
      cursor: pointer;
      transition: box-shadow 200ms ease;
      gap: 12px;
    }

    .row:hover {
      filter: brightness(1.04);
    }

    .row.off {
      --status-color: var(--savant-disabled);
    }

    .row.locked {
      cursor: not-allowed;
      opacity: 0.5;
    }

    .status-bar {
      display: block;
      flex: none;
      width: 7px;
      align-self: stretch;
      border-radius: 999px;
      background: var(--status-color);
    }

    .body {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-width: 0;
      gap: 2px;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }

    .name {
      font-size: 15px;
      font-weight: 500;
      line-height: 1.22;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      text-shadow: var(--savant-text-halo);
      -webkit-text-stroke: 4px var(--savant-text-outline-color);
      paint-order: stroke fill;
    }

    .badge {
      flex: none;
      width: fit-content;
      min-width: 32px;
      height: 20px;
      padding: 0 8px;
      border-radius: 999px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      line-height: 1;
    }

    .badge.on {
      background: var(--savant-success);
      color: white;
    }

    .badge.off {
      background: var(--savant-disabled);
      color: var(--savant-muted);
    }

    .stats {
      display: flex;
      flex-direction: column;
      gap: 1px;
    }

    .stats-line {
      font-size: 12px;
      color: var(--savant-muted);
      line-height: 1.2;
    }

    .stats-line.muted {
      font-style: italic;
    }

    .lock-icon {
      flex: none;
      width: 16px;
      height: 16px;
      align-self: center;
      color: var(--savant-muted);
      opacity: 0.6;
    }

    .lock-icon svg {
      display: block;
      width: 100%;
      height: 100%;
    }
  `;
j([
  d({ type: String })
], E.prototype, "name", 2);
j([
  d({ type: String })
], E.prototype, "entityId", 2);
j([
  d({ type: Boolean })
], E.prototype, "isOn", 2);
j([
  d({ type: Number })
], E.prototype, "averageWatts", 2);
j([
  d({ type: Number })
], E.prototype, "batteryCapacityKwh", 2);
j([
  d({ type: Boolean })
], E.prototype, "loading", 2);
j([
  d({ type: Boolean })
], E.prototype, "controllable", 2);
E = j([
  C("savant-scene-breaker-row")
], E);
var us = Object.defineProperty, gs = Object.getOwnPropertyDescriptor, w = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? gs(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && us(e, s, i), i;
};
let f = class extends y {
  constructor() {
    super(...arguments), this.breakers = [], this.stats = /* @__PURE__ */ new Map(), this.open = !1, this.view = "list", this.scenes = [], this.selectedSceneId = "", this.selectedSceneName = "", this.relayStates = {}, this.newSceneName = "", this.loading = !1, this.saving = !1, this.editingName = !1, this.errorMessage = "", this.searchQuery = "";
  }
  updated(t) {
    t.has("open") && this.open && this.openDialog();
  }
  async openDialog() {
    this.loading = !0, this.errorMessage = "", this.view = "list", this.selectedSceneId = "", this.selectedSceneName = "", this.relayStates = {}, this.newSceneName = "";
    try {
      const t = new U(this.hass);
      this.scenes = await t.fetchScenes();
    } catch {
      this.errorMessage = "Failed to load scenes.";
    } finally {
      this.loading = !1;
    }
  }
  async openEditor(t) {
    this.selectedSceneId = t, this.loading = !0, this.errorMessage = "";
    const e = this.scenes.find((s) => s.id === t);
    this.selectedSceneName = (e == null ? void 0 : e.name) ?? "";
    try {
      const s = new U(this.hass);
      this.relayStates = await s.fetchSceneBreakers(t), this.view = "editor";
    } catch {
      this.errorMessage = "Failed to load scene breakers.";
    } finally {
      this.loading = !1;
    }
  }
  async createScene() {
    const t = this.newSceneName.trim();
    if (t) {
      this.errorMessage = "";
      try {
        const e = new U(this.hass);
        await e.createScene(t, {}), this.scenes = await e.fetchScenes();
        const s = this.scenes.find((r) => r.name === t);
        s && (this.selectedSceneId = s.id, this.selectedSceneName = s.name, this.relayStates = await e.fetchSceneBreakers(s.id), this.view = "editor"), this.newSceneName = "";
      } catch {
        this.errorMessage = "Failed to create scene.";
      }
    }
  }
  async deleteScene(t) {
    if (window.confirm("Delete this scene?")) {
      this.errorMessage = "";
      try {
        const e = new U(this.hass);
        await e.deleteScene(t), this.selectedSceneId === t && (this.selectedSceneId = "", this.selectedSceneName = "", this.relayStates = {}, this.view = "list"), this.scenes = await e.fetchScenes();
      } catch {
        this.errorMessage = "Failed to delete scene.";
      }
    }
  }
  handleToggle(t) {
    t.stopPropagation(), this.relayStates = { ...this.relayStates, [t.detail.entityId]: t.detail.newState };
  }
  async saveScene() {
    if (!(!this.selectedSceneId || !this.selectedSceneName.trim())) {
      this.saving = !0, this.errorMessage = "";
      try {
        const t = new U(this.hass);
        await t.updateScene(this.selectedSceneId, this.selectedSceneName.trim(), this.relayStates), this.scenes = await t.fetchScenes(), this.view = "list";
      } catch {
        this.errorMessage = "Failed to save scene.";
      } finally {
        this.saving = !1;
      }
    }
  }
  async goBack() {
    this.errorMessage = "";
    try {
      const t = new U(this.hass);
      this.scenes = await t.fetchScenes();
    } catch {
    }
    this.view = "list";
  }
  close() {
    this.dispatchEvent(new CustomEvent("savant-scene-close", {}));
  }
  onNewSceneNameInput(t) {
    this.newSceneName = t.target.value;
  }
  onEditorNameInput(t) {
    this.selectedSceneName = t.target.value;
  }
  get filteredScenes() {
    const t = this.searchQuery.trim().toLowerCase();
    return t ? this.scenes.filter((e) => e.name.toLowerCase().includes(t)) : this.scenes;
  }
  get breakerRows() {
    return Object.keys(this.relayStates).map((e) => {
      const s = this.breakers.find(
        (a) => a.entities.switch === e || a.entities.power === e
      ), r = s == null ? void 0 : s.entities.power, i = r ? this.stats.get(r) : void 0;
      return {
        entityId: e,
        name: (s == null ? void 0 : s.name) ?? e,
        isOn: this.relayStates[e] ?? !1,
        averageWatts: i == null ? void 0 : i.averageWatts,
        loading: (i == null ? void 0 : i.loading) ?? !1,
        controllable: (s == null ? void 0 : s.controllable) ?? !1
      };
    }).sort((e, s) => e.name.localeCompare(s.name));
  }
  get footer() {
    const t = /* @__PURE__ */ new Map();
    for (const e of Object.keys(this.relayStates)) {
      const s = this.breakers.find(
        (i) => i.entities.switch === e || i.entities.power === e
      ), r = s == null ? void 0 : s.entities.power;
      r && t.set(e, this.stats.get(r));
    }
    return hs(this.relayStates, t, this.batteryCapacityKwh);
  }
  render() {
    return this.open ? h`
      <div class="scenes-page">
        ${this.view === "list" ? this.renderList() : this.renderEditor()}
      </div>
    ` : v;
  }
  renderList() {
    return h`
      <div class="page-header">
        <span class="page-title">Scenes</span>
        <button class="chip-tool page-close" @click=${this.close} aria-label="Back to breakers">✕</button>
      </div>
      <div class="create-row">
        <input
          class="scene-input"
          type="text"
          placeholder="New scene name..."
          .value=${this.newSceneName}
          @input=${this.onNewSceneNameInput}
          @keydown=${(t) => t.key === "Enter" && this.createScene()}
        />
        <button
          class="scene-action-btn create-btn"
          ?disabled=${!this.newSceneName.trim()}
          @click=${this.createScene}
        >+ Create</button>
      </div>

      ${this.loading ? h`<div class="page-loading">Loading scenes...</div>` : this.filteredScenes.length === 0 ? h`<div class="page-empty"><p>No scenes yet. Create one above.</p></div>` : h`
              <div class="scene-list">
                ${this.filteredScenes.map(
      (t) => h`
                    <div class="scene-tile" role="button" tabindex="0" @click=${() => this.openEditor(t.id)} @keydown=${(e) => e.key === "Enter" && this.openEditor(t.id)}>
                      <span class="scene-tile-bar" aria-hidden="true"></span>
                      <span class="scene-tile-body">
                        <span class="scene-tile-name">${t.name}</span>
                      </span>
                      <button
                        class="scene-delete-btn tile-delete"
                        @click=${(e) => {
        e.stopPropagation(), this.deleteScene(t.id);
      }}
                        aria-label="Delete ${t.name}"
                      >
                        <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                          <path d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z"/>
                        </svg>
                      </button>
                    </div>
                  `
    )}
              </div>
            `}
      ${this.errorMessage ? h`<div class="page-error">${this.errorMessage}</div>` : ""}
    `;
  }
  renderBudgetChip() {
    const t = this.footer;
    if (t.totalOnBreakers === 0)
      return h`<span class="budget-chip"><svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M7.07,18.28C7.5,17.38 10.12,16.5 12,16.5C13.88,16.5 16.5,17.38 16.93,18.28C15.57,19.36 13.86,20 12,20C10.14,20 8.43,19.36 7.07,18.28M18.36,16.83C16.93,15.09 13.46,14.5 12,14.5C10.54,14.5 7.07,15.09 5.64,16.83C4.62,15.5 4,13.82 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,13.82 19.38,15.5 18.36,16.83M12,6C10.06,6 8.5,7.56 8.5,9.5C8.5,11.44 10.06,13 12,13C13.94,13 15.5,11.44 15.5,9.5C15.5,7.56 13.94,6 12,6M12,11C11.17,11 10.5,10.33 10.5,9.5C10.5,8.67 11.17,8 12,8C12.83,8 13.5,8.67 13.5,9.5C13.5,10.33 12.83,11 12,11Z"/></svg> ${t.totalOnBreakers}/${t.totalBreakers} on</span>`;
    const e = [];
    return e.push(`${t.totalOnBreakers}/${t.totalBreakers}`), t.totalKwhPerHour > 0 && e.push(`${it(t.totalKwhPerHour)}/h`), t.batteryDrainPercentPerHour !== void 0 && e.push(at(t.batteryDrainPercentPerHour)), h`
      <span class="budget-chip">
        <svg class="chip-icon" viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
          <path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M7.07,18.28C7.5,17.38 10.12,16.5 12,16.5C13.88,16.5 16.5,17.38 16.93,18.28C15.57,19.36 13.86,20 12,20C10.14,20 8.43,19.36 7.07,18.28M18.36,16.83C16.93,15.09 13.46,14.5 12,14.5C10.54,14.5 7.07,15.09 5.64,16.83C4.62,15.5 4,13.82 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,13.82 19.38,15.5 18.36,16.83M12,6C10.06,6 8.5,7.56 8.5,9.5C8.5,11.44 10.06,13 12,13C13.94,13 15.5,11.44 15.5,9.5C15.5,7.56 13.94,6 12,6M12,11C11.17,11 10.5,10.33 10.5,9.5C10.5,8.67 11.17,8 12,8C12.83,8 13.5,8.67 13.5,9.5C13.5,10.33 12.83,11 12,11Z"/>
        </svg>
        ${e.join(" · ")}
      </span>
    `;
  }
  renderEditor() {
    return h`
      <div class="editor-scroll">
      <div class="page-header">
        <button class="chip-tool page-back" @click=${this.goBack} aria-label="Back to scenes" title="Back to scenes">
          <savant-icon icon="arrow_left" aria-hidden="true"></savant-icon>
        </button>
        <span class="page-title">Edit Scene</span>
        <button
          class="scene-delete-btn header-delete"
          @click=${() => this.deleteScene(this.selectedSceneId)}
          aria-label="Delete scene"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z"/>
          </svg>
        </button>
      </div>
      <div class="editor-name-row">
        ${this.editingName ? h`
            <input class="scene-input" type="text" .value=${this.selectedSceneName} @input=${this.onEditorNameInput} @keydown=${(t) => t.key === "Enter" && (this.editingName = !1)} />
            <button class="icon-btn" @click=${() => this.editingName = !1} aria-label="Done editing">
              <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                <path d="M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z"/>
              </svg>
            </button>
          ` : h`
            <div class="name-group">
              <span class="editor-name-text">${this.selectedSceneName}</span>
              <button class="icon-btn edit-btn" @click=${() => this.editingName = !0} aria-label="Edit scene name">
                <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                  <path d="M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z"/>
                </svg>
              </button>
            </div>
          `}
        
        ${this.renderBudgetChip()}
        
        <button class="icon-btn save-icon-btn" ?disabled=${this.saving} @click=${this.saveScene} aria-label="Save scene" title="Save">
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M15,9H5V5H15M12,19A3,3 0 0,1 9,16A3,3 0 0,1 12,13A3,3 0 0,1 15,16A3,3 0 0,1 12,19M17,3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V7L17,3Z"/>
          </svg>
        </button>
      </div>
      <div class="breaker-list">
        ${this.loading ? h`<div class="page-loading">Loading breakers...</div>` : this.breakerRows.length === 0 ? h`<div class="page-empty"><p>No breakers found.</p></div>` : this.breakerRows.map(
      (t) => h`
                  <savant-scene-breaker-row
                    .name=${t.name}
                    .entityId=${t.entityId}
                    .isOn=${t.isOn}
                    .averageWatts=${t.averageWatts}
                    .batteryCapacityKwh=${this.batteryCapacityKwh}
                    .loading=${t.loading}
                    .controllable=${t.controllable}
                    @savant-scene-toggle=${this.handleToggle}
                  ></savant-scene-breaker-row>
                `
    )}
      </div>
      ${this.errorMessage ? h`<div class="page-error">${this.errorMessage}</div>` : ""}
      </div>
    `;
  }
};
f.styles = [
  ot,
  k`
      :host {
        display: block;
      }

      /* ── Page layout ── */
      .scenes-page {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 0;
      }

      /* ── Page header ── */
      .page-header {
        display: flex;
        align-items: center;
        padding: 0;
        gap: 8px;
      }

      .page-title {
        font-size: 16px;
        font-weight: 600;
        flex: 1;
      }

      .chip-tool {
        flex: none;
        height: 28px;
        width: 28px;
        padding: 0;
        display: grid;
        place-items: center;
        border: 1px solid color-mix(in srgb, var(--primary-text-color) 70%, var(--divider-color));
        border-radius: var(--savant-radius);
        color: var(--primary-text-color);
        background: linear-gradient(
          145deg,
          color-mix(in srgb, var(--savant-tile-bg) 84%, white),
          var(--savant-tile-bg)
        );
        box-shadow:
          inset 0 1px 0 rgb(255 255 255 / 0.14),
          inset 0 0 0 1px color-mix(in srgb, var(--primary-text-color) 18%, transparent),
          0 0 0 1px color-mix(in srgb, var(--ha-card-background, var(--card-background-color)) 56%, white),
          0 2px 5px rgb(0 0 0 / 0.26);
        font-size: 14px;
        line-height: 1;
        cursor: pointer;
        background-color: var(--savant-tile-bg);
      }

      .page-back savant-icon {
        width: 14px;
        height: 14px;
      }

      .chip-tool:hover,
      .chip-tool:focus-visible {
        border-color: color-mix(in srgb, var(--primary-text-color) 82%, white);
        box-shadow:
          inset 0 1px 0 rgb(255 255 255 / 0.2),
          inset 0 0 0 1px color-mix(in srgb, var(--primary-text-color) 30%, transparent),
          0 0 0 1px color-mix(in srgb, var(--primary-text-color) 36%, transparent),
          0 3px 6px rgb(0 0 0 / 0.3);
      }

      /* ── Create row (at top) ── */
      .create-row {
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .scene-input {
        flex: 1;
        background: var(--savant-tile-bg);
        border: 1px solid var(--savant-border);
        border-radius: 8px;
        padding: 8px 12px;
        color: var(--primary-text-color);
        font-size: 14px;
        outline: none;
        font-family: inherit;
      }

      .scene-input:focus {
        border-color: var(--primary-color);
      }

      /* ── Scene action buttons (Create / Save) ── */
      .scene-action-btn {
        padding: 8px 16px;
        border: none;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
        flex: none;
        transition: opacity 200ms ease;
      }

      .create-btn,
      .save-btn {
        background: var(--savant-success);
        color: white;
      }

      .create-btn[disabled],
      .save-btn[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .create-btn:not([disabled]):hover,
      .save-btn:not([disabled]):hover {
        opacity: 0.9;
      }

      /* ── Scene list tiles ── */
      .scene-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .scene-tile {
        display: flex;
        align-items: center;
        box-sizing: border-box;
        overflow: hidden;
        width: 100%;
        padding: 12px 14px;
        text-align: left;
        border: 1px solid var(--savant-border);
        border-radius: var(--savant-radius);
        background: linear-gradient(180deg, color-mix(in srgb, var(--savant-tile-bg-strong) 60%, var(--savant-surface-tint)), var(--savant-tile-bg));
        box-shadow: var(--savant-shadow-sm);
        color: var(--savant-tile-fg);
        cursor: pointer;
        gap: 10px;
        transition: box-shadow 200ms ease;
        font-family: inherit;
        font-size: inherit;
      }

      .scene-tile:hover {
        filter: brightness(1.04);
      }

      .scene-tile-bar {
        display: block;
        flex: none;
        width: 7px;
        align-self: stretch;
        border-radius: 999px;
        background: var(--savant-muted);
      }

      .scene-tile-body {
        flex: 1;
        min-width: 0;
      }

      .scene-tile-name {
        font-size: 15px;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        text-shadow: var(--savant-text-halo);
        -webkit-text-stroke: 4px var(--savant-text-outline-color);
        paint-order: stroke fill;
      }

      /* ── Delete button ── */
      .scene-delete-btn {
        color: var(--savant-error);
        background: none;
        border: none;
        cursor: pointer;
        padding: 4px;
        display: grid;
        place-items: center;
        flex: none;
        border-radius: 4px;
      }

      .scene-delete-btn:hover {
        opacity: 0.8;
      }

      .tile-delete {
        /* specific context within tiles — inherits from .scene-delete-btn */
        width: 28px;
        height: 28px;
        padding: 0;
      }

      .header-delete {
        padding: 6px;
        border-radius: 6px;
        border: 1px solid color-mix(in srgb, var(--savant-error) 50%, transparent);
        background: color-mix(in srgb, var(--savant-error) 8%, transparent);
      }

      .header-delete:hover {
        background: color-mix(in srgb, var(--savant-error) 16%, transparent);
      }

      /* ── Editor scroll container (for sticky header) ── */
      .editor-scroll {
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        flex: 1;
        max-height: 100%;
      }

      /* ── Editor name row (sticky header) ── */
      .editor-name-row {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        border-bottom: 1px solid var(--savant-border);
        min-height: 44px;
        position: sticky;
        top: 0;
        z-index: 2;
        background: var(--savant-card-bg);
      }
      .name-group {
        display: flex;
        align-items: center;
        gap: 4px;
        flex: none;
        max-width: 40%;
        min-width: 0;
      }
      .editor-name-text {
        font-size: 15px;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-width: 0;
      }

      .budget-chip {
        flex: 1;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 10px;
        border: 1px solid color-mix(in srgb, var(--primary-text-color) 70%, var(--divider-color));
        border-radius: var(--savant-radius);
        color: var(--savant-tile-fg);
        background: linear-gradient(
          180deg,
          color-mix(in srgb, var(--savant-tile-bg-strong) 60%, var(--savant-surface-tint)),
          var(--savant-tile-bg)
        );
        box-shadow: var(--savant-shadow-sm);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .chip-icon {
        flex: none;
        opacity: 0.7;
      }

      .icon-btn {
        flex: none;
        width: 28px;
        height: 28px;
        padding: 0;
        display: grid;
        place-items: center;
        border: 1px solid transparent;
        border-radius: var(--savant-radius);
        background: transparent;
        color: var(--savant-muted);
        cursor: pointer;
        transition: color 200ms ease, border-color 200ms ease;
      }
      .icon-btn:hover {
        color: var(--primary-text-color);
        border-color: var(--savant-border);
      }
      .save-icon-btn {
        background: var(--savant-success);
        color: white;
        border: 1px solid var(--savant-success);
        border-radius: var(--savant-radius);
        width: 32px;
        height: 32px;
      }
      .save-icon-btn:hover {
        background: color-mix(in srgb, var(--savant-success) 80%, black);
        color: white;
        border-color: var(--savant-success);
      }
      .save-icon-btn[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
        background: var(--savant-disabled);
        border-color: var(--savant-disabled);
      }
      .edit-btn {
        color: var(--savant-muted);
      }

      /* ── Breaker list ── */
      .breaker-list {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 6px;
        flex: 1;
        padding: 8px 12px;
      }

      /* ── Info / error states ── */
      .page-loading,
      .page-empty {
        padding: 32px 16px;
        text-align: center;
        color: var(--savant-muted);
      }

      .page-error {
        padding: 8px 0;
        color: var(--savant-error);
        font-size: 12px;
      }
    `
];
w([
  d({ attribute: !1 })
], f.prototype, "hass", 2);
w([
  d({ attribute: !1 })
], f.prototype, "breakers", 2);
w([
  d({ attribute: !1 })
], f.prototype, "stats", 2);
w([
  d({ type: Number })
], f.prototype, "batteryCapacityKwh", 2);
w([
  d({ type: Boolean, reflect: !0 })
], f.prototype, "open", 2);
w([
  g()
], f.prototype, "view", 2);
w([
  g()
], f.prototype, "scenes", 2);
w([
  g()
], f.prototype, "selectedSceneId", 2);
w([
  g()
], f.prototype, "selectedSceneName", 2);
w([
  g()
], f.prototype, "relayStates", 2);
w([
  g()
], f.prototype, "newSceneName", 2);
w([
  g()
], f.prototype, "loading", 2);
w([
  g()
], f.prototype, "saving", 2);
w([
  g()
], f.prototype, "editingName", 2);
w([
  g()
], f.prototype, "errorMessage", 2);
w([
  d({ type: String })
], f.prototype, "searchQuery", 2);
f = w([
  C("savant-scene-dialog")
], f);
class vs {
  constructor(e) {
    this.manualBreakers = e;
  }
  async discover(e) {
    return this.manualBreakers.map((s) => {
      const r = {
        switch: s.switch_entity,
        power: s.power_entity,
        energy: s.energy_entity,
        voltage: s.voltage_entity,
        current: s.current_entity
      };
      return {
        id: `manual:${s.id}`,
        name: s.name,
        areaName: s.area_name,
        panelName: s.panel_name,
        circuitNumber: s.circuit_number,
        controllable: !!s.switch_entity,
        entities: r,
        available: Object.values(r).some(
          (i) => {
            var a;
            return i && ((a = e.states[i]) == null ? void 0 : a.state) !== "unavailable";
          }
        ),
        discoveryConfidence: "manual"
      };
    });
  }
}
function nt(t, e) {
  const s = t.split(".")[0], r = e == null ? void 0 : e.attributes.device_class;
  if (s === "switch") return "switch";
  if (s === "sensor") {
    if (r === "power") return "power";
    if (r === "energy") return "energy";
    if (r === "voltage") return "voltage";
    if (r === "current") return "current";
  }
}
function ms(t) {
  var o;
  const e = new Map(t.devices.map((n) => [n.id, n])), s = new Map(t.areas.map((n) => [n.area_id, n.name])), r = /* @__PURE__ */ new Map(), i = [];
  for (const n of t.entities)
    if (!(n.disabled_by || n.hidden_by) && fs(n, e.get(n.device_id ?? ""), t.integration))
      if (n.device_id) {
        const l = r.get(n.device_id) ?? [];
        l.push(n), r.set(n.device_id, l);
      } else
        i.push(n);
  const a = [];
  for (const [n, l] of r) {
    const c = bs(n, l, e.get(n), s, t.states);
    c && a.push(c);
  }
  for (const n of i) {
    const l = nt(n.entity_id, t.states[n.entity_id]);
    l && a.push({
      id: $s(n),
      name: lt(n, t.states[n.entity_id]),
      areaId: n.area_id,
      areaName: n.area_id ? s.get(n.area_id) : void 0,
      controllable: l === "switch",
      entities: { [l]: n.entity_id },
      available: ((o = t.states[n.entity_id]) == null ? void 0 : o.state) !== "unavailable",
      discoveryConfidence: "medium",
      discoveryNotes: ["Associated from entity registry without a device_id."]
    });
  }
  return a;
}
function fs(t, e, s) {
  var a;
  if (t.platform === s) return !0;
  const r = ((e == null ? void 0 : e.manufacturer) ?? "").toLowerCase(), i = ((a = e == null ? void 0 : e.identifiers) == null ? void 0 : a.flat().join(" ").toLowerCase()) ?? "";
  return r.includes("savant") || i.includes(s.toLowerCase());
}
function bs(t, e, s, r, i) {
  var S;
  const a = {}, o = [];
  for (const A of e) {
    const L = nt(A.entity_id, i[A.entity_id]);
    !L || a[L] || (a[L] = A.entity_id);
  }
  if (!Object.keys(a).length) return;
  const n = e.find((A) => A.entity_id === a.power) ?? e[0], l = (n == null ? void 0 : n.area_id) ?? (s == null ? void 0 : s.area_id) ?? void 0, c = n ? (S = i[n.entity_id]) == null ? void 0 : S.attributes : {}, u = _s((c == null ? void 0 : c.circuit_number) ?? (c == null ? void 0 : c.circuit)), p = xs(c == null ? void 0 : c.panel_name, c == null ? void 0 : c.panel, s == null ? void 0 : s.model), m = ys(s, e), _ = m ? ws(e, i) : void 0;
  return a.power || o.push("No power sensor with device_class: power was found."), a.switch || o.push("No switch entity was found for breaker control."), {
    id: `device:${t}`,
    deviceId: t,
    name: (s == null ? void 0 : s.name_by_user) || (s == null ? void 0 : s.name) || lt(n, n ? i[n.entity_id] : void 0),
    areaId: l,
    areaName: l ? r.get(l) : void 0,
    panelName: p,
    circuitNumber: u,
    controllable: !!a.switch,
    entities: a,
    available: Object.values(a).some((A) => {
      var L;
      return ((L = i[A]) == null ? void 0 : L.state) !== "unavailable";
    }),
    discoveryConfidence: a.power && a.switch ? "high" : "medium",
    discoveryNotes: o.length ? o : void 0,
    isSem: m,
    semMetrics: _
  };
}
function ys(t, e) {
  const s = `${(t == null ? void 0 : t.name) ?? ""} ${(t == null ? void 0 : t.name_by_user) ?? ""} ${(t == null ? void 0 : t.model) ?? ""} ${(t == null ? void 0 : t.manufacturer) ?? ""}`.toLowerCase();
  return s.includes("sem") || s.includes("energy monitor") || s.includes("energy hub") ? !0 : e.some((r) => `${r.name ?? ""} ${r.original_name ?? ""} ${r.entity_id}`.toLowerCase().includes("sem"));
}
function ws(t, e) {
  var r, i;
  const s = {};
  for (const a of t) {
    const o = e[a.entity_id], n = `${a.name ?? ""} ${a.original_name ?? ""} ${((r = o == null ? void 0 : o.attributes) == null ? void 0 : r.friendly_name) ?? ""} ${a.entity_id}`.toLowerCase(), l = String(((i = o == null ? void 0 : o.attributes) == null ? void 0 : i.device_class) ?? "").toLowerCase();
    !s.homeLoad && /(home|total).*(load|consumption)|consumption|house load/.test(n) && (s.homeLoad = a.entity_id), !s.solar && /solar|pv/.test(n) && (s.solar = a.entity_id), !s.grid && /grid|utility|mains/.test(n) && (s.grid = a.entity_id), !s.batterySoc && (l === "battery" || /soc|state.?of.?charge|battery.*%/.test(n)) && (s.batterySoc = a.entity_id), !s.batteryPower && /battery/.test(n) && !/soc|state.?of.?charge|%/.test(n) && (s.batteryPower = a.entity_id);
  }
  return Object.values(s).some(Boolean) ? s : void 0;
}
function xs(...t) {
  return t.find((e) => typeof e == "string" && e.length > 0);
}
function _s(t) {
  const e = Number(t);
  return Number.isFinite(e) ? e : void 0;
}
function $s(t) {
  return t.unique_id ? `entity:${t.unique_id}` : `entity:${t.entity_id}`;
}
function lt(t, e) {
  return (t == null ? void 0 : t.name) || (t == null ? void 0 : t.original_name) || (e == null ? void 0 : e.attributes.friendly_name) || (t == null ? void 0 : t.entity_id) || "Savant breaker";
}
class ks {
  constructor(e) {
    this.integration = e;
  }
  async discover(e) {
    const s = await Ss(e);
    return ms({
      ...s,
      states: e.states,
      integration: this.integration
    });
  }
}
async function Ss(t) {
  const e = t.connection;
  if (!(e != null && e.sendMessagePromise))
    return { entities: [], devices: [], areas: [] };
  const [s, r, i] = await Promise.all([
    e.sendMessagePromise({ type: "config/entity_registry/list" }),
    e.sendMessagePromise({ type: "config/device_registry/list" }),
    e.sendMessagePromise({ type: "config/area_registry/list" })
  ]);
  return {
    entities: s,
    devices: r,
    areas: i
  };
}
class ct {
  constructor(e) {
    this.providers = e;
  }
  async discover(e, s) {
    const r = this.providers ?? [
      ...s.discovery.enabled ? [new ks(s.discovery.integration)] : [],
      new vs(s.manual_breakers)
    ], i = await Promise.all(r.map((a) => a.discover(e)));
    return As(i.flat());
  }
}
function As(t) {
  const e = /* @__PURE__ */ new Map();
  for (const s of t) {
    const r = e.get(s.id);
    e.set(
      s.id,
      r ? {
        ...r,
        ...s,
        entities: { ...r.entities, ...s.entities },
        discoveryNotes: [...r.discoveryNotes ?? [], ...s.discoveryNotes ?? []]
      } : s
    );
  }
  return [...e.values()];
}
class Cs {
  async fetchHistory(e, s, r) {
    var l;
    if (!((l = e.connection) != null && l.sendMessagePromise)) return [];
    const i = /* @__PURE__ */ new Date(), a = new Date(i.getTime() - Ps(r)), o = await e.connection.sendMessagePromise({
      type: "history/history_during_period",
      start_time: a.toISOString(),
      end_time: i.toISOString(),
      entity_ids: [s],
      minimal_response: !0,
      no_attributes: !0
    });
    return ((o == null ? void 0 : o[0]) ?? []).map((c) => ({
      start: new Date(c.last_changed ?? c.lu ?? c.s).getTime(),
      value: Number(c.state)
    })).filter((c) => Number.isFinite(c.start) && Number.isFinite(c.value));
  }
}
function Ps(t) {
  switch (t) {
    case "1h":
      return 3600 * 1e3;
    case "6h":
      return 360 * 60 * 1e3;
    case "12h":
      return 720 * 60 * 1e3;
    case "7d":
      return 10080 * 60 * 1e3;
    case "24h":
    default:
      return 1440 * 60 * 1e3;
  }
}
class Ms {
  constructor() {
    this.cache = /* @__PURE__ */ new Map(), this.history = new Cs();
  }
  async getStatistics(e, s, r, i) {
    const a = `${s}:${r}`, o = Date.now(), n = this.cache.get(a);
    if (n && o - n.fetchedAt < i * 1e3)
      return n.data;
    try {
      const l = await this.fetchStatisticsOrHistory(e, s, r), c = l.map((p) => p.value).filter(Number.isFinite), u = {
        entityId: s,
        period: r,
        points: l,
        averageWatts: c.length ? c.reduce((p, m) => p + m, 0) / c.length : void 0,
        maximumWatts: c.length ? Math.max(...c) : void 0,
        loading: !1,
        fetchedAt: o
      };
      return this.cache.set(a, { data: u, fetchedAt: o }), u;
    } catch (l) {
      return {
        entityId: s,
        period: r,
        points: [],
        loading: !1,
        error: l instanceof Error ? l.message : "History unavailable"
      };
    }
  }
  invalidate(e) {
    if (!e) {
      this.cache.clear();
      return;
    }
    for (const s of this.cache.keys())
      s.startsWith(`${e}:`) && this.cache.delete(s);
  }
  async fetchStatisticsOrHistory(e, s, r) {
    var i;
    if (!((i = e.connection) != null && i.sendMessagePromise)) return [];
    if (r === "7d" || r === "24h" || r === "12h" || r === "6h")
      try {
        const a = /* @__PURE__ */ new Date(), o = new Date(a.getTime() - Es(r)), n = await e.connection.sendMessagePromise({
          type: "recorder/statistics_during_period",
          start_time: o.toISOString(),
          end_time: a.toISOString(),
          statistic_ids: [s],
          period: r === "7d" ? "hour" : "5minute",
          types: ["mean", "max"]
        }), c = ((n == null ? void 0 : n[s]) ?? []).map((u) => ({
          start: new Date(u.start).getTime(),
          value: Number(u.mean ?? u.max)
        })).filter((u) => Number.isFinite(u.start) && Number.isFinite(u.value));
        if (c.length) return c;
      } catch {
      }
    return this.history.fetchHistory(e, s, r);
  }
}
function Es(t) {
  switch (t) {
    case "7d":
      return 10080 * 60 * 1e3;
    case "6h":
      return 360 * 60 * 1e3;
    case "12h":
      return 720 * 60 * 1e3;
    case "1h":
      return 3600 * 1e3;
    default:
      return 1440 * 60 * 1e3;
  }
}
const N = {
  type: "custom:savant-energy-breaker-board-card",
  title: "Electrical Panel",
  discovery: {
    enabled: !0,
    integration: "savant_energy",
    include_new_breakers: !0,
    panel_filter: null,
    area_filter: null
  },
  layout: {
    group_by: "none",
    sort_by: "circuit_number",
    density: "comfortable",
    mobile_view: "standard"
  },
  display: {
    show_title: !0,
    hide_sem_chip: !0,
    show_current_power: !0,
    show_average_power: !0,
    show_maximum_power: !0,
    show_energy: !1,
    show_sparkline: !0,
    show_icon: !0,
    show_state: !0,
    show_controls: !0,
    show_area: !0,
    show_circuit_number: !0
  },
  graph: {
    period: "24h",
    refresh_interval_seconds: 300
  },
  controls: {
    default_mode: "hold_confirm_off",
    warning_load_threshold_watts: 1e3,
    high_load_threshold_watts: 2e3
  },
  excluded_breakers: [],
  breaker_overrides: {},
  manual_breakers: [],
  scenes: { enabled: !0, battery_capacity_kwh: void 0 }
}, ht = {
  title: "Title",
  discovery: "Discovery",
  enabled: "Auto-discovery",
  integration: "Integration domain",
  include_new_breakers: "Show new breakers automatically",
  panel_filter: "Panel filter",
  area_filter: "Area filter",
  layout: "Layout",
  group_by: "Group by",
  sort_by: "Sort by",
  current_power_descending: "Highest current power",
  highest_usage: "Highest usage",
  density: "Density",
  mobile_view: "Mobile view",
  display: "Default tile details",
  show_title: "Title section",
  hide_sem_chip: "Hide SEM chip",
  show_current_power: "Current power",
  show_average_power: "Average power",
  show_maximum_power: "Maximum power",
  show_energy: "Energy",
  show_sparkline: "Sparkline",
  show_icon: "Icon",
  show_state: "Breaker state",
  show_controls: "Breaker controls",
  show_area: "Area label",
  show_circuit_number: "Circuit number",
  graph: "Graph",
  period: "History period",
  refresh_interval_seconds: "Refresh interval",
  controls: "Controls",
  default_mode: "Default safety mode",
  warning_load_threshold_watts: "Yellow chart threshold",
  high_load_threshold_watts: "Orange chart threshold",
  manual_breakers: "Manual breaker mappings",
  id: "Breaker ID",
  name: "Name",
  switch_entity: "Switch entity",
  power_entity: "Power entity",
  energy_entity: "Energy entity",
  voltage_entity: "Voltage entity",
  current_entity: "Current entity",
  area_name: "Area name",
  panel_name: "Panel name",
  circuit_number: "Circuit number",
  scenes: "Scenes",
  battery_capacity_kwh: "Battery capacity (kWh)"
}, Os = {
  integration: "Defaults to savant_energy and is used to match registry metadata.",
  panel_filter: "Optional exact panel name to include.",
  area_filter: "Optional exact area name to include.",
  refresh_interval_seconds: "Minimum 30 seconds.",
  warning_load_threshold_watts: "Chart turns yellow above this wattage.",
  high_load_threshold_watts: "Chart turns orange above this wattage.",
  manual_breakers: "Optional fallback mappings for breakers that cannot be discovered from entity metadata.",
  id: "Use a stable ID, for example panel_1_circuit_12.",
  battery_capacity_kwh: "Set to show battery drain estimates in scene editor."
};
function Ls() {
  return {
    schema: [
      { name: "title", selector: { text: {} } },
      { name: "battery_capacity_kwh", selector: { number: { min: 0, step: 0.1, mode: "box", unit_of_measurement: "kWh" } } },
      {
        type: "expandable",
        name: "discovery",
        title: "Discovery",
        schema: [
          { name: "enabled", selector: { boolean: {} } },
          { name: "integration", selector: { text: {} } },
          { name: "include_new_breakers", selector: { boolean: {} } },
          { name: "panel_filter", selector: { text: {} } },
          { name: "area_filter", selector: { text: {} } }
        ]
      },
      {
        type: "expandable",
        name: "layout",
        title: "Layout",
        schema: [
          K("group_by", ["none", "panel", "area", "panel_then_area"]),
          K("sort_by", ["circuit_number", "name", "current_power_descending", "highest_usage", "manual"]),
          K("density", ["comfortable", "compact"]),
          K("mobile_view", ["standard", "ultra_compact"])
        ]
      },
      {
        type: "expandable",
        name: "display",
        title: "Default Tile Details",
        schema: [
          { name: "show_title", selector: { boolean: {} } },
          { name: "hide_sem_chip", selector: { boolean: {} } },
          { name: "show_current_power", selector: { boolean: {} } },
          { name: "show_average_power", selector: { boolean: {} } },
          { name: "show_maximum_power", selector: { boolean: {} } },
          { name: "show_energy", selector: { boolean: {} } },
          { name: "show_sparkline", selector: { boolean: {} } },
          { name: "show_icon", selector: { boolean: {} } },
          { name: "show_state", selector: { boolean: {} } },
          { name: "show_controls", selector: { boolean: {} } },
          { name: "show_area", selector: { boolean: {} } },
          { name: "show_circuit_number", selector: { boolean: {} } }
        ]
      },
      {
        type: "expandable",
        name: "graph",
        title: "Graph",
        schema: [
          K("period", ["1h", "6h", "12h", "24h", "7d"]),
          {
            name: "refresh_interval_seconds",
            selector: { number: { min: 30, step: 30, mode: "box", unit_of_measurement: "s" } }
          }
        ]
      },
      {
        type: "expandable",
        name: "controls",
        title: "Controls",
        schema: [
          K("default_mode", ["hidden", "hold", "hold_confirm_off"]),
          {
            name: "warning_load_threshold_watts",
            selector: { number: { min: 0, step: 100, mode: "box", unit_of_measurement: "W" } }
          },
          {
            name: "high_load_threshold_watts",
            selector: { number: { min: 0, step: 100, mode: "box", unit_of_measurement: "W" } }
          }
        ]
      },
      {
        type: "expandable",
        name: "manual",
        title: "Manual Breaker Mappings",
        flatten: !0,
        schema: [
          {
            name: "manual_breakers",
            selector: {
              object: {
                multiple: !0,
                label_field: "name",
                description_field: "id",
                fields: {
                  id: { required: !0, selector: { text: {} } },
                  name: { required: !0, selector: { text: {} } },
                  switch_entity: J("switch"),
                  power_entity: J("sensor"),
                  energy_entity: J("sensor"),
                  voltage_entity: J("sensor"),
                  current_entity: J("sensor"),
                  area_name: { selector: { text: {} } },
                  panel_name: { selector: { text: {} } },
                  circuit_number: {
                    selector: { number: { min: 0, step: 1, mode: "box" } }
                  }
                }
              }
            }
          }
        ]
      }
    ],
    computeLabel: (t) => ht[t.name],
    computeHelper: (t) => Os[t.name],
    assertConfig: Bs
  };
}
function J(t) {
  return {
    selector: {
      entity: {
        filter: { domain: t }
      }
    }
  };
}
function K(t, e) {
  return {
    name: t,
    selector: {
      select: {
        mode: "dropdown",
        options: e.map((s) => ({ value: s, label: ht[s] ?? Ns(s) }))
      }
    }
  };
}
function Ns(t) {
  return t.split("_").map((e) => e.charAt(0).toUpperCase() + e.slice(1)).join(" ");
}
function Bs(t) {
  if (Z("discovery", t.discovery), Z("layout", t.layout), Z("display", t.display), Z("graph", t.graph), Z("controls", t.controls), t.excluded_breakers !== void 0 && !Array.isArray(t.excluded_breakers))
    throw new Error("excluded_breakers must be a list.");
  if (t.manual_breakers !== void 0 && !Array.isArray(t.manual_breakers))
    throw new Error("manual_breakers must be a list.");
  if (Z("breaker_overrides", t.breaker_overrides), t.scenes !== void 0 && (typeof t.scenes != "object" || t.scenes === null || Array.isArray(t.scenes)))
    throw new Error("scenes must be an object.");
}
function Z(t, e) {
  if (e !== void 0 && (e === null || Array.isArray(e) || typeof e != "object"))
    throw new Error(`${t} must be an object.`);
}
function dt(t, e) {
  const s = { ...t };
  if (!e) return s;
  for (const [r, i] of Object.entries(e))
    Array.isArray(i) ? s[r] = [...i] : i && typeof i == "object" && !Array.isArray(i) ? s[r] = dt(s[r] ?? {}, i) : i !== void 0 && (s[r] = i);
  return s;
}
const Hs = /* @__PURE__ */ new Set(["1h", "6h", "12h", "24h", "7d"]), Ts = /* @__PURE__ */ new Set(["standard", "ultra_compact"]);
function ie(t) {
  const e = dt(N, t ?? {});
  e.discovery.enabled = e.discovery.enabled !== !1, e.discovery.integration = e.discovery.integration || N.discovery.integration, e.discovery.include_new_breakers = e.discovery.include_new_breakers !== !1, Ts.has(e.layout.mobile_view) || (e.layout.mobile_view = N.layout.mobile_view), e.display.show_title = e.display.show_title !== !1, Hs.has(e.graph.period) || (e.graph.period = N.graph.period), e.graph.refresh_interval_seconds = Math.max(30, Number(e.graph.refresh_interval_seconds) || 300);
  const s = Number(e.controls.warning_load_threshold_watts);
  e.controls.warning_load_threshold_watts = Math.max(
    0,
    Number.isFinite(s) ? s : N.controls.warning_load_threshold_watts || 1e3
  );
  const r = Number(e.controls.high_load_threshold_watts);
  return e.controls.high_load_threshold_watts = Math.max(
    0,
    Number.isFinite(r) ? r : N.controls.high_load_threshold_watts || 2e3
  ), e.excluded_breakers = Array.isArray(e.excluded_breakers) ? [...new Set(e.excluded_breakers)] : [], e.breaker_overrides = e.breaker_overrides ?? {}, e.scenes = e.scenes ?? { enabled: !0 }, e.scenes.enabled = e.scenes.enabled !== !1, (typeof e.scenes.battery_capacity_kwh != "number" || e.scenes.battery_capacity_kwh <= 0) && (e.scenes.battery_capacity_kwh = void 0), e.manual_breakers = Array.isArray(e.manual_breakers) ? e.manual_breakers : [], e;
}
function Ds(t, e) {
  const s = t.breaker_overrides[e.id] ?? {};
  return {
    label: s.label || e.name,
    show_current_power: s.show_current_power ?? t.display.show_current_power,
    show_average_power: s.show_average_power ?? t.display.show_average_power,
    show_maximum_power: s.show_maximum_power ?? t.display.show_maximum_power,
    show_energy: s.show_energy ?? t.display.show_energy,
    show_sparkline: s.show_sparkline ?? t.display.show_sparkline,
    show_icon: s.show_icon ?? t.display.show_icon,
    show_state: t.display.show_state,
    show_controls: s.show_controls ?? t.display.show_controls,
    show_area: t.display.show_area,
    show_circuit_number: t.display.show_circuit_number,
    control_mode: s.control_mode ?? t.controls.default_mode
  };
}
var zs = Object.defineProperty, js = Object.getOwnPropertyDescriptor, x = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? js(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && zs(e, s, i), i;
};
let b = class extends y {
  constructor() {
    super(...arguments), this.config = N, this.breakers = [], this.loading = !0, this.error = "", this.stats = /* @__PURE__ */ new Map(), this.pendingSwitches = /* @__PURE__ */ new Set(), this.toggleErrors = /* @__PURE__ */ new Map(), this.stacked = !1, this.sortMenuOpen = !1, this.activePage = "breakers", this.searchOpen = !1, this.searchQuery = "", this.optimisticSwitchStates = /* @__PURE__ */ new Map(), this.discovery = new ct(), this.statistics = new Ms(), this.discoveryKey = "", this.statsRefreshToken = 0, this.optimisticResetTimers = /* @__PURE__ */ new Map(), this.handleToggle = async (t) => {
      var l;
      if (t.stopPropagation(), !this.hass) return;
      const e = this.breakers.find((c) => c.id === t.detail.breakerId), s = e == null ? void 0 : e.entities.switch;
      if (!e || !s || this.pendingSwitches.has(e.id)) return;
      const i = (this.optimisticSwitchStates.get(e.id) ?? ((l = this.hass.states[s]) == null ? void 0 : l.state)) === "on" ? "off" : "on";
      this.setOptimisticSwitchState(e.id, i), this.pendingSwitches = /* @__PURE__ */ new Set([...this.pendingSwitches, e.id]), this.toggleErrors.delete(e.id);
      let a = !1;
      try {
        await this.hass.callService("switch", i === "off" ? "turn_off" : "turn_on", { entity_id: s }), a = !0;
      } catch {
        this.clearOptimisticSwitchState(e.id);
        const c = new Map(this.toggleErrors);
        c.set(e.id, "Failed to toggle"), this.toggleErrors = c;
      } finally {
        const c = new Set(this.pendingSwitches);
        c.delete(e.id), this.pendingSwitches = c;
      }
      if (!a) return;
      const o = this.optimisticResetTimers.get(e.id);
      o !== void 0 && window.clearTimeout(o);
      const n = window.setTimeout(() => {
        this.clearOptimisticSwitchState(e.id);
      }, 15e3);
      this.optimisticResetTimers.set(e.id, n);
    };
  }
  setConfig(t) {
    this.config = ie(t), this.runtimeSortBy = this.loadPersistedSort() ?? this.config.layout.sort_by, this.runtimeMobileView = this.loadPersistedMobileView() ?? this.config.layout.mobile_view, this.setAttribute("density", this.config.layout.density), this.setAttribute("mobile-view", this.effectiveMobileView()), this.discoveryKey = "";
  }
  static getConfigElement() {
    return document.createElement("savant-energy-breaker-board-card-editor");
  }
  static getConfigForm() {
    return Ls();
  }
  static getStubConfig() {
    return {
      title: "Electrical Panel",
      discovery: { enabled: !0 },
      layout: { group_by: "none", density: "comfortable", mobile_view: "standard" }
    };
  }
  getCardSize() {
    const t = Math.max(this.breakers.length, 6);
    return Math.ceil(t / 2) + (this.config.display.show_title && this.config.title ? 1 : 0);
  }
  getGridOptions() {
    return {
      columns: "full",
      min_columns: 6,
      rows: Math.max(4, Math.ceil(Math.max(this.breakers.length, 6) / 3) * 4),
      min_rows: 4
    };
  }
  firstUpdated() {
    this.resizeObserver = new ResizeObserver(([t]) => {
      if (!t) {
        this.stacked = !1;
        return;
      }
      this.updateStackedLayout(t.contentRect.width);
    }), this.observeLayoutTarget();
  }
  disconnectedCallback() {
    var t;
    super.disconnectedCallback(), (t = this.resizeObserver) == null || t.disconnect();
    for (const e of this.optimisticResetTimers.values())
      window.clearTimeout(e);
    this.optimisticResetTimers.clear();
  }
  updated(t) {
    this.observeLayoutTarget(), (t.has("hass") || t.has("config")) && this.ensureDiscovered();
  }
  observeLayoutTarget() {
    if (!this.resizeObserver) return;
    const t = this.renderRoot.querySelector(".board-grid") ?? this.renderRoot.querySelector("ha-card") ?? this;
    t !== this.resizeTarget && (this.resizeTarget && this.resizeObserver.unobserve(this.resizeTarget), this.resizeTarget = t, this.resizeObserver.observe(t), this.updateStackedLayout(t.getBoundingClientRect().width));
  }
  updateStackedLayout(t) {
    !Number.isFinite(t) || t <= 0 || (this.stacked && t >= 560 && (this.stacked = !1), !this.stacked && t <= 520 && (this.stacked = !0));
  }
  render() {
    return h`
      <ha-card>
        ${this.config.display.show_title ? this.renderHeader() : v}
        ${this.activePage === "scenes" ? this.renderScenesPage() : this.error ? h`<savant-board-error-state .message=${this.error}></savant-board-error-state>` : this.loading ? this.renderSkeletons() : this.visibleBreakers().length ? this.renderBreakers() : h`<savant-board-empty-state></savant-board-empty-state>`}
      </ha-card>
    `;
  }
  renderSkeletons() {
    return h`<div class=${`board-grid ${this.stacked ? "stacked" : ""}`}>${Array.from(
      { length: 8 },
      () => h`<savant-breaker-tile-skeleton ?stacked=${this.stacked}></savant-breaker-tile-skeleton>`
    )}</div>`;
  }
  renderHeader() {
    return h`
      <div class="board-header">
        <div class="board-header-top">
          <div class="savant-wordmark" aria-label="Savant">SAVANT</div>
          <div class="board-tools">
            ${this.stacked ? h`<button
                  class=${this.effectiveMobileView() === "ultra_compact" ? "chip-tool active" : "chip-tool"}
                  type="button"
                  @click=${() => this.toggleMobileView()}
                >
                  <savant-icon icon="minimize_2" aria-hidden="true"></savant-icon>
                  <span class="sr-only">Toggle ultra-compact mobile view</span>
                </button>` : v}
            <div class="tool-wrap">
              <button
                class=${this.searchOpen ? "chip-tool active" : "chip-tool"}
                type="button"
                @click=${() => this.searchOpen = !this.searchOpen}
              >
                <savant-icon icon="search" aria-hidden="true"></savant-icon>
                <span class="sr-only">Search</span>
              </button>
            </div>
            <div class="tool-wrap">
              <button class="chip-tool" type="button" @click=${() => this.sortMenuOpen = !this.sortMenuOpen}>
                <savant-icon icon="sort_amount_down" aria-hidden="true"></savant-icon>
                <span class="sr-only">Sort</span>
              </button>
              ${this.sortMenuOpen ? h`<div class="tool-popover">
                    ${Ue.map(
      ({ value: t, label: e }) => h`
                        <button
                          class=${this.effectiveSortBy() === t ? "menu-option selected" : "menu-option"}
                          type="button"
                          @click=${() => this.setRuntimeSort(t)}
                        >
                          ${e}
                        </button>
                      `
    )}
                  </div>` : v}
            </div>
            ${this.scenesConfig.enabled !== !1 ? h`<div class="tool-wrap">
                  <button
                    class="chip-tool${this.activePage === "scenes" ? " active" : ""}"
                    type="button"
                    @click=${this.toggleScenePage}
                    aria-label="Scenes"
                  >
                    <savant-icon icon="layout_dashboard" aria-hidden="true"></savant-icon>
                    <span class="sr-only">Scenes</span>
                  </button>
                </div>` : v}
          </div>
        </div>
        ${this.searchOpen ? h`<div class="board-search-row" role="search" aria-label="Search loads">
              <div class="board-search-shell">
                <savant-icon icon="search" aria-hidden="true"></savant-icon>
                <input
                  class="search-input"
                  type="search"
                  placeholder=${this.activePage === "scenes" ? "Search scenes" : "Search loads"}
                  .value=${this.searchQuery}
                  @input=${(t) => this.searchQuery = t.target.value}
                />
              </div>
            </div>` : v}
      </div>
    `;
  }
  renderBreakers() {
    const t = this.visibleSemBreakers(), e = Is(this.visibleStandardBreakers(), this.config);
    return h`
      <div
        class=${`board-grid ${this.stacked ? "stacked" : ""}`}
        @savant-breaker-toggle=${this.handleToggle}
      >
        ${t.map(
      (s) => h`<savant-sem-chip .hass=${this.hass} .breaker=${s}></savant-sem-chip>`
    )}
        ${e.map(
      ([s, r]) => h`
            ${s ? h`<h3 class="group-title">${s}</h3>` : v}
            ${r.map((i) => {
        const a = Ds(this.config, i), o = i.entities.power, n = o ? this.stats.get(o) : void 0;
        return h`<savant-breaker-tile
                .hass=${this.hass}
                .breaker=${i}
                .display=${a}
                .statistics=${n}
                ?stacked=${this.stacked}
                .mobileLayout=${this.effectiveMobileView()}
                .optimisticSwitchState=${this.optimisticSwitchStates.get(i.id)}
                .graphLoading=${!!(o && !n)}
                .pending=${this.pendingSwitches.has(i.id)}
                .error=${this.toggleErrors.get(i.id) ?? ""}
                .warningLoadThresholdWatts=${this.config.controls.warning_load_threshold_watts ?? 1e3}
                .highLoadThresholdWatts=${this.config.controls.high_load_threshold_watts ?? 2e3}
              ></savant-breaker-tile>`;
      })}
          `
    )}
      </div>
    `;
  }
  async ensureDiscovered() {
    if (!this.hass) return;
    const t = JSON.stringify({
      discovery: this.config.discovery,
      manual: this.config.manual_breakers
    });
    if (t === this.discoveryKey && this.breakers.length) {
      this.loadStatistics();
      return;
    }
    this.loading = !0, this.error = "";
    try {
      this.breakers = await this.discovery.discover(this.hass, this.config), this.discoveryKey = t, this.loading = !1, this.stats = /* @__PURE__ */ new Map(), this.loadStatistics();
    } catch (e) {
      this.error = e instanceof Error ? e.message : "Discovery failed", this.loading = !1;
    }
  }
  async loadStatistics() {
    if (!this.hass) return;
    const t = ++this.statsRefreshToken, e = [
      ...new Set(
        this.visibleStandardBreakers().map((r) => r.entities.power).filter((r) => !!r)
      )
    ], s = await Promise.all(
      e.map(async (r) => [
        r,
        await this.statistics.getStatistics(
          this.hass,
          r,
          this.config.graph.period,
          this.config.graph.refresh_interval_seconds
        )
      ])
    );
    t === this.statsRefreshToken && (this.stats = new Map(s));
  }
  visibleBreakers() {
    const t = new Set(this.config.excluded_breakers), e = this.searchQuery.trim().toLowerCase(), s = this.breakers.filter((r) => t.has(r.id) ? !1 : e ? [r.name, r.areaName, r.panelName].filter(Boolean).some((i) => i.toLowerCase().includes(e)) : !0);
    return Rs(
      s,
      this.config,
      this.hass,
      this.stats,
      this.effectiveSortBy()
    );
  }
  visibleStandardBreakers() {
    return this.visibleBreakers().filter((t) => !t.isSem);
  }
  visibleSemBreakers() {
    return this.config.display.hide_sem_chip ? [] : this.visibleBreakers().filter((t) => t.isSem);
  }
  get scenesConfig() {
    return this.config.scenes ?? { enabled: !0 };
  }
  effectiveSortBy() {
    return this.runtimeSortBy ?? this.config.layout.sort_by;
  }
  effectiveMobileView() {
    return this.runtimeMobileView ?? this.config.layout.mobile_view;
  }
  setRuntimeSort(t) {
    var e;
    this.runtimeSortBy = t, this.sortMenuOpen = !1, (e = window.localStorage) == null || e.setItem(this.persistedSortKey(), t);
  }
  toggleMobileView() {
    var e;
    const t = this.effectiveMobileView() === "ultra_compact" ? "standard" : "ultra_compact";
    this.runtimeMobileView = t, this.setAttribute("mobile-view", t), (e = window.localStorage) == null || e.setItem(this.persistedMobileViewKey(), t);
  }
  loadPersistedSort() {
    var e;
    const t = (e = window.localStorage) == null ? void 0 : e.getItem(this.persistedSortKey());
    return Ue.some((s) => s.value === t) ? t ?? void 0 : void 0;
  }
  loadPersistedMobileView() {
    var e;
    const t = (e = window.localStorage) == null ? void 0 : e.getItem(this.persistedMobileViewKey());
    return t === "standard" || t === "ultra_compact" ? t : void 0;
  }
  persistedSortKey() {
    return `savant-breaker-board-sort:${this.config.title ?? "default"}`;
  }
  persistedMobileViewKey() {
    return `savant-breaker-board-mobile-view:${this.config.title ?? "default"}`;
  }
  setOptimisticSwitchState(t, e) {
    const s = this.optimisticResetTimers.get(t);
    s !== void 0 && (window.clearTimeout(s), this.optimisticResetTimers.delete(t)), this.optimisticSwitchStates = new Map(this.optimisticSwitchStates), this.optimisticSwitchStates.set(t, e);
  }
  clearOptimisticSwitchState(t) {
    const e = this.optimisticResetTimers.get(t);
    if (e !== void 0 && (window.clearTimeout(e), this.optimisticResetTimers.delete(t)), !this.optimisticSwitchStates.has(t)) return;
    const s = new Map(this.optimisticSwitchStates);
    s.delete(t), this.optimisticSwitchStates = s;
  }
  toggleScenePage(t) {
    t.stopPropagation(), this.activePage = this.activePage === "scenes" ? "breakers" : "scenes";
  }
  renderScenesPage() {
    return h`
      <savant-scene-dialog
        .hass=${this.hass}
        .breakers=${this.breakers}
        .stats=${this.stats}
        .batteryCapacityKwh=${this.scenesConfig.battery_capacity_kwh}
        .searchQuery=${this.searchQuery}
        .open=${this.activePage === "scenes"}
        @savant-scene-close=${this.closeScenesPage}
      ></savant-scene-dialog>
    `;
  }
  closeScenesPage() {
    this.activePage = "breakers";
  }
};
b.styles = [
  ot,
  k`
      :host([density="compact"]) {
        --tile-height: 158px;
      }

      .board-header {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 8px;
        width: 100%;
        padding-bottom: 10px;
      }

      .board-header-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        width: 100%;
        min-width: 0;
      }

      .board-tools {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-left: auto;
      }

      .savant-wordmark {
        font-size: 26px;
        line-height: 36px;
        height: 36px;
        font-weight: 800;
        letter-spacing: 0;
        color: var(--primary-text-color);
      }

      .tool-wrap {
        position: relative;
      }

      .chip-tool {
        height: 36px;
        width: 36px;
        padding: 0;
        display: grid;
        place-items: center;
        border: 1px solid color-mix(in srgb, var(--primary-text-color) 70%, var(--divider-color));
        border-radius: var(--savant-radius);
        color: var(--primary-text-color);
        background: var(--savant-tile-bg);
        box-shadow: var(--savant-shadow-sm);
        font-size: 18px;
        line-height: 1;
        cursor: pointer;
      }

      .chip-tool savant-icon {
        width: 20px;
        height: 20px;
      }

      .chip-tool:hover,
      .chip-tool:focus-visible {
        border-color: color-mix(in srgb, var(--primary-text-color) 82%, white);
        box-shadow: var(--savant-shadow-md);
      }

      .chip-tool.active {
        border-color: color-mix(in srgb, var(--primary-color) 84%, var(--primary-text-color));
        box-shadow: var(--savant-shadow-md);
      }

      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }

      .board-search-row {
        display: block;
        width: 100%;
      }

      .board-search-shell {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        box-sizing: border-box;
        min-height: 36px;
        padding: 0 12px;
        border: 1px solid var(--savant-border);
        border-radius: var(--savant-radius);
        background: var(--savant-tile-bg);
        box-shadow: var(--savant-shadow-sm);
      }

      .board-search-shell savant-icon {
        width: 18px;
        height: 18px;
        color: color-mix(in srgb, var(--primary-text-color) 75%, var(--secondary-text-color));
        flex: none;
      }

      .board-search-shell .search-input {
        flex: 1;
        width: 100%;
        min-width: 0;
        padding: 9px 0;
        border: 0;
        outline: none;
        color: var(--primary-text-color);
        background: transparent;
      }

      .tool-popover {
        position: absolute;
        right: 0;
        top: calc(100% + 6px);
        z-index: 10;
        display: grid;
        gap: 4px;
        min-width: 190px;
        padding: 8px;
        border: 1px solid var(--savant-border-strong);
        border-radius: var(--savant-radius);
        background: var(--savant-card-bg);
        box-shadow: var(--savant-shadow-md);
      }

      .menu-option {
        padding: 8px 10px;
        border: 0;
        border-radius: 8px;
        color: var(--primary-text-color);
        background: transparent;
        text-align: left;
        cursor: pointer;
      }

      .menu-option.selected,
      .menu-option:hover {
        background: color-mix(in srgb, var(--savant-tile-bg) 92%, var(--primary-text-color));
      }

      .search-input {
        box-sizing: border-box;
      }
    `
];
x([
  d({ attribute: !1 })
], b.prototype, "hass", 2);
x([
  g()
], b.prototype, "config", 2);
x([
  g()
], b.prototype, "breakers", 2);
x([
  g()
], b.prototype, "loading", 2);
x([
  g()
], b.prototype, "error", 2);
x([
  g()
], b.prototype, "stats", 2);
x([
  g()
], b.prototype, "pendingSwitches", 2);
x([
  g()
], b.prototype, "toggleErrors", 2);
x([
  g()
], b.prototype, "stacked", 2);
x([
  g()
], b.prototype, "sortMenuOpen", 2);
x([
  g()
], b.prototype, "activePage", 2);
x([
  g()
], b.prototype, "searchOpen", 2);
x([
  g()
], b.prototype, "searchQuery", 2);
x([
  g()
], b.prototype, "runtimeSortBy", 2);
x([
  g()
], b.prototype, "runtimeMobileView", 2);
x([
  g()
], b.prototype, "optimisticSwitchStates", 2);
b = x([
  C("savant-energy-breaker-board-card")
], b);
const Ue = [
  { value: "circuit_number", label: "Circuit number" },
  { value: "name", label: "Name" },
  { value: "current_power_descending", label: "Current power" },
  { value: "highest_usage", label: "Highest usage" },
  { value: "manual", label: "Manual" }
];
function Rs(t, e, s, r = /* @__PURE__ */ new Map(), i = e.layout.sort_by) {
  return [...t].sort((a, o) => {
    var n, l;
    if (i === "name") return a.name.localeCompare(o.name);
    if (i === "current_power_descending") {
      const c = z(a.entities.power ? (n = s == null ? void 0 : s.states[a.entities.power]) == null ? void 0 : n.state : void 0) ?? -1 / 0;
      return (z(o.entities.power ? (l = s == null ? void 0 : s.states[o.entities.power]) == null ? void 0 : l.state : void 0) ?? -1 / 0) - c;
    }
    if (i === "highest_usage") {
      const c = Ke(a, r, s);
      return Ke(o, r, s) - c || a.name.localeCompare(o.name);
    }
    return i === "manual" ? 0 : (a.circuitNumber ?? 9999) - (o.circuitNumber ?? 9999) || a.name.localeCompare(o.name);
  });
}
function Ke(t, e, s) {
  var i, a;
  const r = t.entities.power;
  return r ? ((i = e.get(r)) == null ? void 0 : i.averageWatts) ?? z((a = s == null ? void 0 : s.states[r]) == null ? void 0 : a.state) ?? -1 / 0 : -1 / 0;
}
function Is(t, e) {
  if (e.layout.group_by === "none") return [["", t]];
  const s = /* @__PURE__ */ new Map();
  for (const r of t) {
    const i = e.layout.group_by === "panel_then_area" ? [r.panelName, r.areaName].filter(Boolean).join(" / ") || "Other" : e.layout.group_by === "area" ? r.areaName || "Other" : r.panelName || "Other";
    s.set(i, [...s.get(i) ?? [], r]);
  }
  return [...s.entries()];
}
function pt(t, e) {
  if (Array.isArray(t))
    return t.length ? t : void 0;
  if (t && typeof t == "object") {
    const s = {};
    for (const [r, i] of Object.entries(t)) {
      const a = pt(i, e == null ? void 0 : e[r]);
      a !== void 0 && (s[r] = a);
    }
    return Object.keys(s).length ? s : void 0;
  }
  return t === e ? void 0 : t;
}
function ut(t) {
  const e = ie(t);
  return {
    type: "custom:savant-energy-breaker-board-card",
    ...pt(e, N) ?? {}
  };
}
function Fs(t, e) {
  const s = structuredClone(t);
  return delete s.breaker_overrides[e], ut(s);
}
var Vs = Object.defineProperty, Ws = Object.getOwnPropertyDescriptor, R = (t, e, s, r) => {
  for (var i = r > 1 ? void 0 : r ? Ws(e, s) : e, a = t.length - 1, o; a >= 0; a--)
    (o = t[a]) && (i = (r ? o(e, s, i) : o(i)) || i);
  return r && i && Vs(e, s, i), i;
};
let O = class extends y {
  constructor() {
    super(...arguments), this.config = N, this.breakers = [], this.filter = "", this.loading = !1, this.discoveryError = "", this.expandedBreakers = /* @__PURE__ */ new Set(), this.discoveryLoaded = !1, this.discovery = new ct();
  }
  setConfig(t) {
    this.config = ie(t), this.loadBreakers();
  }
  updated(t) {
    t.has("hass") && this.loadBreakers();
  }
  render() {
    const t = this.breakers.filter(
      (e) => e.name.toLowerCase().includes(this.filter.toLowerCase())
    );
    return h`
      <div class="editor">
        <section>
          <h3>Board</h3>
          ${this.textInput("Title", this.config.title ?? "", (e) => this.patch({ title: e || void 0 }))}
          ${this.switch(
      "Show title section",
      this.config.display.show_title,
      (e) => this.patch({ display: { ...this.config.display, show_title: e } })
    )}
          ${this.switch(
      "Hide SEM chip",
      this.config.display.hide_sem_chip,
      (e) => this.patch({ display: { ...this.config.display, hide_sem_chip: e } })
    )}
          ${this.switch(
      "Auto-discovery",
      this.config.discovery.enabled,
      (e) => this.patch({ discovery: { ...this.config.discovery, enabled: e } })
    )}
          ${this.switch(
      "Ultra-compact mobile view",
      this.config.layout.mobile_view === "ultra_compact",
      (e) => this.patch({ layout: { ...this.config.layout, mobile_view: e ? "ultra_compact" : "standard" } })
    )}
          ${this.switch(
      "Group by breaker type",
      this.config.layout.group_by !== "none",
      (e) => this.patch({ layout: { ...this.config.layout, group_by: e ? "panel" : "none" } })
    )}
          ${this.select(
      "Sort",
      this.config.layout.sort_by,
      ["circuit_number", "name", "current_power_descending", "highest_usage", "manual"],
      (e) => this.patch({ layout: { ...this.config.layout, sort_by: e } })
    )}
          ${this.select(
      "Density",
      this.config.layout.density,
      ["comfortable", "compact"],
      (e) => this.patch({ layout: { ...this.config.layout, density: e } })
    )}
          ${this.select(
      "Graph period",
      this.config.graph.period,
      ["1h", "6h", "12h", "24h", "7d"],
      (e) => this.patch({ graph: { ...this.config.graph, period: e } })
    )}
          <p class="helper">Tiles automatically switch to a horizontal stacked layout in narrow dashboard columns.</p>
        </section>

        <section>
          <h3>Defaults</h3>
          ${Object.entries({
      show_current_power: "Current power",
      show_average_power: "Average power",
      show_maximum_power: "Maximum power",
      show_energy: "Energy",
      show_sparkline: "Sparkline",
      show_icon: "Icon",
      show_state: "Breaker state",
      show_controls: "Breaker controls",
      show_area: "Area label",
      show_circuit_number: "Circuit number"
    }).map(
      ([e, s]) => this.switch(
        s,
        this.config.display[e],
        (r) => this.patch({ display: { ...this.config.display, [e]: r } })
      )
    )}
          ${this.select(
      "Control safety",
      this.config.controls.default_mode,
      ["hidden", "hold", "hold_confirm_off"],
      (e) => this.patch({ controls: { ...this.config.controls, default_mode: e } })
    )}
          ${this.numberInput(
      "Yellow chart threshold (W)",
      this.config.controls.warning_load_threshold_watts ?? 1e3,
      (e) => this.patch({ controls: { ...this.config.controls, warning_load_threshold_watts: e } })
    )}
          ${this.numberInput(
      "Orange chart threshold (W)",
      this.config.controls.high_load_threshold_watts ?? 2e3,
      (e) => this.patch({ controls: { ...this.config.controls, high_load_threshold_watts: e } })
    )}
        </section>

        <section>
          <div class="section-head">
            <h3>Discovered breakers</h3>
            <button class="refresh" ?disabled=${this.loading || !this.hass} @click=${() => this.loadBreakers(!0)}>
              ${this.loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
          ${this.textInput("Search breakers", this.filter, (e) => this.filter = e, !1)}
          ${this.discoveryError ? h`<div class="error">${this.discoveryError}</div>` : v}
          ${this.loading ? h`<div class="loading">Loading discovered breakers...</div>` : v}
          ${!this.loading && !t.length ? h`<div class="loading">${this.discoveryLoaded ? "No discovered breakers found." : "Discovery will run once when Home Assistant is ready."}</div>` : v}
          ${t.map((e) => this.renderBreakerEditor(e))}
        </section>
      </div>
    `;
  }
  renderBreakerEditor(t) {
    var o, n;
    const e = this.config.excluded_breakers.includes(t.id), s = this.config.breaker_overrides[t.id] ?? {}, r = this.expandedBreakers.has(t.id), i = t.entities.power ? z((n = (o = this.hass) == null ? void 0 : o.states[t.entities.power]) == null ? void 0 : n.state) : void 0, a = Object.entries(t.entities).filter(([, l]) => l).map(([l, c]) => `${l}: ${c}`).join(", ");
    return h`
      <article class=${e ? "breaker excluded" : "breaker"}>
        <div class="breaker-head" @click=${() => this.toggleExpanded(t.id)}>
          <div>
            <strong>${s.label || t.name}</strong>
          </div>
          <span class="breaker-actions">
            ${this.switch("Shown", !e, (l) => this.setExcluded(t.id, !l))}
            <span class="chevron">${r ? "Collapse" : "Expand"}</span>
          </span>
        </div>
        ${r ? h`
              <div class="breaker-details">
                <span>${re(i)} - ${t.available ? "available" : "unavailable"}</span>
                <small>${a || "No associated entities"}</small>
              </div>
              ${this.textInput(
      "Custom label",
      s.label ?? "",
      (l) => this.setOverride(t.id, { ...s, label: l || void 0 })
    )}
              <div class="override-grid">
                ${["show_current_power", "show_average_power", "show_maximum_power", "show_energy", "show_sparkline", "show_icon", "show_controls"].map(
      (l) => this.tristate(
        l.replaceAll("_", " "),
        s[l],
        (c) => this.setOverride(t.id, { ...s, [l]: c })
      )
    )}
              </div>
              ${this.select(
      "Control mode",
      s.control_mode ?? "default",
      ["default", "hidden", "hold", "hold_confirm_off"],
      (l) => this.setOverride(t.id, {
        ...s,
        control_mode: l === "default" ? void 0 : l
      })
    )}
              <button class="reset" @click=${() => this.resetOverride(t.id)}>Reset to defaults</button>
            ` : v}
      </article>
    `;
  }
  async loadBreakers(t = !1) {
    if (!(!this.hass || !t && (this.discoveryLoaded || this.loading))) {
      this.loading = !0, this.discoveryError = "";
      try {
        this.breakers = await this.discovery.discover(this.hass, this.config), this.discoveryLoaded = !0;
      } catch (e) {
        this.discoveryError = e instanceof Error ? e.message : "Discovery failed";
      } finally {
        this.loading = !1;
      }
    }
  }
  patch(t) {
    this.config = ie({ ...this.config, ...t }), ce(this, "config-changed", { config: ut(this.config) });
  }
  setExcluded(t, e) {
    const s = new Set(this.config.excluded_breakers);
    e ? s.add(t) : s.delete(t), this.patch({ excluded_breakers: [...s] });
  }
  setOverride(t, e) {
    const s = Object.fromEntries(Object.entries(e).filter(([, r]) => r !== void 0 && r !== ""));
    this.patch({ breaker_overrides: { ...this.config.breaker_overrides, [t]: s } });
  }
  resetOverride(t) {
    const e = Fs(this.config, t);
    this.config = ie(e), ce(this, "config-changed", { config: e });
  }
  toggleExpanded(t) {
    const e = new Set(this.expandedBreakers);
    e.has(t) ? e.delete(t) : e.add(t), this.expandedBreakers = e;
  }
  textInput(t, e, s, r = !0) {
    return h`<label><span>${t}</span><input .value=${e} @input=${(i) => s(i.target.value)} @change=${r ? (i) => s(i.target.value) : void 0} /></label>`;
  }
  checkbox(t, e, s) {
    return h`<label class="check"><input type="checkbox" .checked=${e} @change=${(r) => s(r.target.checked)} /> <span>${t}</span></label>`;
  }
  switch(t, e, s) {
    return h`
      <label class="switch" @click=${(r) => r.stopPropagation()}>
        <input type="checkbox" .checked=${e} @change=${(r) => s(r.target.checked)} />
        <span class="switch-track" aria-hidden="true"></span>
        <span>${t}</span>
      </label>
    `;
  }
  select(t, e, s, r) {
    return h`<label><span>${t}</span><select .value=${e} @change=${(i) => r(i.target.value)}>${s.map((i) => h`<option value=${i}>${i}</option>`)}</select></label>`;
  }
  numberInput(t, e, s) {
    return h`<label><span>${t}</span><input type="number" min="0" step="100" .value=${String(e)} @change=${(r) => s(Number(r.target.value) || 0)} /></label>`;
  }
  tristate(t, e, s) {
    const r = e === void 0 ? "default" : String(e);
    return this.select(
      t,
      r,
      ["default", "true", "false"],
      (i) => s(i === "default" ? void 0 : i === "true")
    );
  }
};
O.styles = k`
    .editor {
      display: grid;
      gap: 18px;
    }

    section,
    .breaker {
      display: grid;
      gap: 10px;
      padding: 12px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
    }

    h3 {
      margin: 0;
      font-size: 16px;
    }

    label {
      display: grid;
      gap: 4px;
      font-size: 13px;
    }

    input,
    select {
      box-sizing: border-box;
      width: 100%;
      padding: 8px;
      color: var(--primary-text-color);
      background: var(--secondary-background-color);
      border: 1px solid var(--divider-color);
      border-radius: 6px;
    }

    .check {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .check input {
      width: auto;
    }

    .switch {
      display: flex;
      align-items: center;
      gap: 9px;
      width: max-content;
      max-width: 100%;
      cursor: pointer;
    }

    .switch input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }

    .switch-track {
      position: relative;
      flex: none;
      width: 36px;
      height: 20px;
      border-radius: 999px;
      background: var(--disabled-text-color);
      transition: background 150ms ease;
    }

    .switch-track::after {
      content: "";
      position: absolute;
      top: 3px;
      left: 3px;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: var(--card-background-color, white);
      transition: transform 150ms ease;
      box-shadow: 0 1px 2px rgb(0 0 0 / 0.25);
    }

    .switch input:checked + .switch-track {
      background: var(--primary-color);
    }

    .switch input:checked + .switch-track::after {
      transform: translateX(16px);
    }

    .helper,
    .loading,
    small,
    .breaker span {
      color: var(--secondary-text-color);
    }

    .error {
      color: var(--error-color);
      font-size: 13px;
    }

    .section-head,
    .breaker-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .breaker-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      cursor: pointer;
    }

    .breaker-head div {
      display: grid;
      gap: 3px;
      min-width: 0;
    }

    .breaker-details {
      display: grid;
      gap: 3px;
      min-width: 0;
    }

    .chevron {
      font-size: 12px;
      color: var(--secondary-text-color);
    }

    .excluded {
      opacity: 0.62;
    }

    .override-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 8px;
    }

    .reset,
    .refresh {
      justify-self: start;
      padding: 8px 10px;
      border: 1px solid var(--divider-color);
      border-radius: 6px;
      color: var(--primary-text-color);
      background: var(--secondary-background-color);
      cursor: pointer;
    }

    .refresh {
      justify-self: end;
      padding: 6px 10px;
    }

    .refresh:disabled {
      opacity: 0.6;
      cursor: default;
    }
  `;
R([
  d({ attribute: !1 })
], O.prototype, "hass", 2);
R([
  g()
], O.prototype, "config", 2);
R([
  g()
], O.prototype, "breakers", 2);
R([
  g()
], O.prototype, "filter", 2);
R([
  g()
], O.prototype, "loading", 2);
R([
  g()
], O.prototype, "discoveryError", 2);
R([
  g()
], O.prototype, "expandedBreakers", 2);
O = R([
  C("savant-energy-breaker-board-card-editor")
], O);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "savant-energy-breaker-board-card",
  name: "Savant Energy Card",
  description: "Discover and control Savant Energy breaker/circuit power data.",
  preview: !0,
  documentationURL: "https://github.com/bballdavis/Savant-Card"
});

})();
