# -*- coding: utf-8 -*-
"""着色器源码"""

# ============================================================ 天空 + 云
SKY_VS = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uInvVP;
uniform vec3 uCamPos;
out vec3 vDir;
void main() {
    // aPos 是 NDC 全屏四边形
    vec4 p = uInvVP * vec4(aPos.xy, 1.0, 1.0);
    vDir = normalize(p.xyz / p.w - uCamPos);
    gl_Position = vec4(aPos.xy, 0.9999, 1.0);
}
"""

SKY_FS = """
#version 330 core
in vec3 vDir;
uniform vec3 uCamPos;
uniform vec3 uSunDir;
uniform float uTime;
uniform float uCloudCover;
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
    float h = clamp(d.y, -1.0, 1.0);
    vec3 zenith = vec3(0.16, 0.34, 0.68);
    vec3 horizon = vec3(0.68, 0.80, 0.92);
    vec3 ground = vec3(0.30, 0.30, 0.28);
    vec3 sky = mix(horizon, zenith, pow(clamp(h, 0.0, 1.0), 0.62));
    if (h < 0.0) {
        sky = mix(horizon, ground, clamp(-h * 3.0, 0.0, 1.0));
    }

    // ---------- 太阳
    float sd = max(dot(d, normalize(uSunDir)), 0.0);
    // 太阳盘
    float disc = smoothstep(0.99930, 0.99975, sd);
    // 光晕
    float glow = pow(sd, 420.0) * 0.9 + pow(sd, 22.0) * 0.16;
    vec3 sunCol = vec3(1.0, 0.95, 0.84);
    sky += sunCol * glow;
    sky = mix(sky, vec3(1.4, 1.34, 1.16), disc);

    // ---------- 云层（在一个平面上做体积近似）
    if (d.y > 0.012) {
        float planeH = 1500.0;
        float t = planeH / d.y;
        vec2 uv = (uCamPos.xz + d.xz * t) * 0.00042;
        uv += vec2(uTime * 0.0035, uTime * 0.0018);

        float base = fbm(uv * 1.6);
        float detail = fbm(uv * 5.3 + 3.1);
        float shape = base * 0.72 + detail * 0.34;

        float cover = uCloudCover;
        float clouds = smoothstep(cover, cover + 0.24, shape);

        // 云的明暗
        float light = smoothstep(cover, cover + 0.55, shape + detail * 0.22);
        vec3 cloudDark = vec3(0.55, 0.60, 0.68);
        vec3 cloudLit = vec3(1.0, 0.99, 0.96);
        vec3 cloudCol = mix(cloudDark, cloudLit, light);

        // 地平线附近云变暗、被大气雾吃掉
        float fade = smoothstep(0.012, 0.14, d.y);
        clouds *= fade;
        // 太阳方向的银边
        float rim = pow(max(dot(d, normalize(uSunDir)), 0.0), 6.0) * 0.35;
        cloudCol += sunCol * rim * clouds;

        sky = mix(sky, cloudCol, clouds * 0.94);
    }

    // ---------- 地平线雾
    float haze = exp(-max(d.y, 0.0) * 9.0);
    sky = mix(sky, vec3(0.72, 0.80, 0.90), haze * 0.55);

    FragColor = vec4(sky, 1.0);
}
"""

# ============================================================ 物体（飞机/建筑）
OBJ_VS = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec3 aColor;
uniform mat4 uVP;
uniform mat4 uModel;
uniform mat3 uNormalMat;
out vec3 vNormal;
out vec3 vColor;
out vec3 vWorld;
void main() {
    vec4 wp = uModel * vec4(aPos, 1.0);
    vWorld = wp.xyz;
    vNormal = normalize(uNormalMat * aNormal);
    vColor = aColor;
    gl_Position = uVP * wp;
}
"""

OBJ_FS = """
#version 330 core
in vec3 vNormal;
in vec3 vColor;
in vec3 vWorld;
uniform vec3 uSunDir;
uniform vec3 uCamPos;
uniform vec3 uFogColor;
uniform float uFogDensity;
out vec4 FragColor;
void main() {
    vec3 N = normalize(vNormal);
    vec3 L = normalize(uSunDir);
    float diff = max(dot(N, L), 0.0);
    // 半兰伯特让背光面不至于全黑
    float wrapped = diff * 0.78 + 0.22 * max(dot(N, L) * 0.5 + 0.5, 0.0);
    vec3 ambient = vec3(0.34, 0.38, 0.46);
    vec3 col = vColor * (ambient + wrapped * vec3(1.06, 1.02, 0.96));

    // 高光（金属感）
    vec3 V = normalize(uCamPos - vWorld);
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), 42.0) * 0.28;
    col += vec3(spec);

    // 距离雾
    float dist = length(uCamPos - vWorld);
    float fog = 1.0 - exp(-dist * uFogDensity);
    col = mix(col, uFogColor, clamp(fog, 0.0, 0.94));

    FragColor = vec4(col, 1.0);
}
"""

# ============================================================ 实例化物体（树/房屋/水面点缀）
INST_VS = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec3 aColor;
layout(location = 3) in vec3 iPos;      // 实例：世界位置
layout(location = 4) in float iScale;   // 实例：缩放
layout(location = 5) in float iYaw;     // 实例：绕 Y 轴旋转
layout(location = 6) in vec3 iTint;     // 实例：颜色微调
uniform mat4 uVP;
out vec3 vNormal;
out vec3 vColor;
out vec3 vWorld;
void main() {
    float c = cos(iYaw), s = sin(iYaw);
    // 先缩放，再绕 Y 转，再平移到实例位置
    vec3 p = aPos * iScale;
    vec3 rp = vec3(p.x * c + p.z * s, p.y, -p.x * s + p.z * c);
    vec3 n = aNormal;
    vec3 rn = vec3(n.x * c + n.z * s, n.y, -n.x * s + n.z * c);
    vec4 wp = vec4(rp + iPos, 1.0);
    vWorld = wp.xyz;
    vNormal = normalize(rn);
    vColor = aColor * iTint;
    gl_Position = uVP * wp;
}
"""

INST_FS = """
#version 330 core
in vec3 vNormal;
in vec3 vColor;
in vec3 vWorld;
uniform vec3 uSunDir;
uniform vec3 uCamPos;
uniform vec3 uFogColor;
uniform float uFogDensity;
out vec4 FragColor;
void main() {
    vec3 N = normalize(vNormal);
    vec3 L = normalize(uSunDir);
    float diff = max(dot(N, L), 0.0);
    float wrapped = diff * 0.70 + 0.30 * (dot(N, L) * 0.5 + 0.5);
    vec3 ambient = vec3(0.32, 0.37, 0.44);
    vec3 col = vColor * (ambient + wrapped * vec3(1.04, 1.02, 0.95));

    float dist = length(uCamPos - vWorld);
    float fog = 1.0 - exp(-dist * uFogDensity);
    col = mix(col, uFogColor, clamp(fog, 0.0, 0.96));
    FragColor = vec4(col, 1.0);
}
"""

# ============================================================ 半透明水面
# 注意：水面不能用 INST_VS！那是实例化着色器，要用 location 3~6 的实例属性。
# 水面网格没有这些属性，默认值 (0,0,0,1) 会把所有顶点缩到原点，什么都画不出来。
WATER_VS = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec3 aColor;
uniform mat4 uVP;
uniform mat4 uModel;
out vec3 vNormal;
out vec3 vColor;
out vec3 vWorld;
void main() {
    vec4 wp = uModel * vec4(aPos, 1.0);
    vWorld = wp.xyz;
    vNormal = aNormal;
    vColor = aColor;
    gl_Position = uVP * wp;
}
"""

WATER_FS = """
#version 330 core
in vec3 vNormal;
in vec3 vColor;
in vec3 vWorld;
uniform vec3 uSunDir;
uniform vec3 uCamPos;
uniform vec3 uFogColor;
uniform float uFogDensity;
out vec4 FragColor;
void main() {
    vec3 N = normalize(vNormal);
    vec3 L = normalize(uSunDir);
    vec3 V = normalize(uCamPos - vWorld);
    float diff = max(dot(N, L), 0.0);

    // 天光反射（菲涅尔）：掠角越大越像镜子
    float fres = pow(1.0 - max(dot(N, V), 0.0), 2.2);
    vec3 deep  = vec3(0.13, 0.40, 0.60);   // 深水蓝
    vec3 shade = vec3(0.06, 0.22, 0.36);   // 阴面更深的蓝
    vec3 sky   = vec3(0.62, 0.79, 0.95);   // 反射天光
    vec3 col = mix(shade, deep, diff * 0.6 + 0.4);
    col = mix(col, sky, fres * 0.80);

    // 太阳高光（水面闪光）
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), 90.0) * 0.9;
    col += vec3(1.0, 0.97, 0.88) * spec;

    float dist = length(uCamPos - vWorld);
    float fog = 1.0 - exp(-dist * uFogDensity);
    col = mix(col, uFogColor, clamp(fog, 0.0, 0.92));

    float alpha = mix(0.86, 1.0, clamp(fog * 1.5, 0.0, 1.0));
    FragColor = vec4(col, alpha);
}
"""

# ============================================================ 地形
TERRAIN_VS = OBJ_VS

TERRAIN_FS = """
#version 330 core
in vec3 vNormal;
in vec3 vColor;
in vec3 vWorld;
uniform vec3 uSunDir;
uniform vec3 uCamPos;
uniform vec3 uFogColor;
uniform float uFogDensity;
out vec4 FragColor;

void main() {
    vec3 N = normalize(vNormal);
    vec3 L = normalize(uSunDir);
    float diff = max(dot(N, L), 0.0);
    float wrapped = diff * 0.72 + 0.28 * (dot(N, L) * 0.5 + 0.5);
    vec3 ambient = vec3(0.30, 0.35, 0.42);
    vec3 col = vColor * (ambient + wrapped * vec3(1.05, 1.02, 0.94));

    // 远处细节柔化
    float dist = length(uCamPos - vWorld);
    float fog = 1.0 - exp(-dist * uFogDensity);
    col = mix(col, uFogColor, clamp(fog, 0.0, 0.96));

    FragColor = vec4(col, 1.0);
}
"""
