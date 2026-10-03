# -*- coding: utf-8 -*-
"""
天空着色器（重写版）
用相机基向量构造射线，不依赖矩阵求逆 —— 更稳、更容易排错。
"""
SKY_VS = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform vec3 uRight;
uniform vec3 uUp;
uniform vec3 uFwd;
uniform float uTanHalfFov;
uniform float uAspect;
out vec3 vDir;
void main() {
    vec2 ndc = aPos.xy;
    vec3 dir = uFwd
             + uRight * (ndc.x * uTanHalfFov * uAspect)
             + uUp    * (ndc.y * uTanHalfFov);
    vDir = normalize(dir);
    gl_Position = vec4(ndc, 0.9999, 1.0);
}
"""

SKY_FS = """
#version 330 core
in vec3 vDir;
uniform vec3 uSunDir;
uniform float uTime;
uniform float uCloudCover;
uniform float uCloudHeight;
uniform vec3 uCamPos;
uniform float uSunGlow;
out vec4 FragColor;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 6; i++) {
        v += a * vnoise(p);
        p = p * 2.03 + vec2(11.3, 7.7);
        a *= 0.5;
    }
    return v;
}

void main() {
    vec3 d = normalize(vDir);

    // ---------- 天空渐变
    vec3 zenith  = vec3(0.13, 0.30, 0.66);
    vec3 horizon = vec3(0.72, 0.82, 0.93);
    vec3 ground  = vec3(0.24, 0.26, 0.25);
    vec3 col;
    if (d.y >= 0.0) {
        col = mix(horizon, zenith, pow(clamp(d.y, 0.0, 1.0), 0.55));
    } else {
        col = mix(horizon, ground, clamp(-d.y * 4.0, 0.0, 1.0));
    }

    // ---------- 太阳
    vec3 sd = normalize(uSunDir);
    float cosang = dot(d, sd);
    if (uSunGlow > 0.5) {
        float disc = smoothstep(0.99930, 0.99975, cosang);
        float glow = pow(max(cosang, 0.0), 380.0) * 0.85
                   + pow(max(cosang, 0.0), 18.0) * 0.18;
        col += vec3(1.0, 0.96, 0.86) * glow;
        col = mix(col, vec3(1.5, 1.42, 1.22), disc);
    }

    // ---------- 云层
    // 用视线方向角做采样（不用平面投影，避免靠近云层高度时出现奇点条纹）
    if (d.y > 0.008) {
        vec2 uv = d.xz / max(d.y + 0.14, 0.10);
        uv = uv * 0.55 + vec2(uTime * 0.006, uTime * 0.0022);
        float base = fbm(uv * 1.05);
        float det  = fbm(uv * 3.4 + 5.1);
        float shape = base * 0.78 + det * 0.30;
        float cover = uCloudCover;
        float clouds = smoothstep(cover, cover + 0.30, shape);
        float light  = smoothstep(cover, cover + 0.62, shape + det * 0.22);
        vec3 cloudDark = vec3(0.46, 0.53, 0.64);
        vec3 cloudLit  = vec3(1.0, 0.995, 0.97);
        vec3 cloudCol = mix(cloudDark, cloudLit, light);
        // 地平线附近云层淡出
        clouds *= smoothstep(0.008, 0.10, d.y);
        // 太阳方向银边
        cloudCol += vec3(1.0, 0.95, 0.84) * pow(max(cosang, 0.0), 5.0) * 0.35 * clouds;
        col = mix(col, cloudCol, clouds * 0.95);
    }

    // ---------- 地平线雾
    col = mix(col, vec3(0.74, 0.82, 0.91), exp(-max(d.y, 0.0) * 8.0) * 0.5);

    FragColor = vec4(col, 1.0);
}
"""
