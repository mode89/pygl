#! vim: ft=paimel

# Minimal rendering engine built on ModernGL.

import math
import struct
import moderngl
import glm
import builtins as py

# Primitive types

def TRIANGLES = moderngl.TRIANGLES
def LINES = moderngl.LINES
def LINE_STRIP = moderngl.LINE_STRIP
def POINTS = moderngl.POINTS

# --- Data classes ---

class DirectLight direction color:[1.0, 1.0, 1.0] intensity:1.0

class Environment
  clearColor:[0.0, 0.0, 0.0, 1.0]
  time:0.0
  ambient:[0.1, 0.1, 0.1]
  viewport:[0, 0, 800, 600]
  light:nil
  cullFace:false

class Camera
  position:[0.0, 0.0, 1.0]
  orientation:[0.0, 0.0, 0.0]
  fov:60.0
  aspect:1.0
  near:0.1
  far:100.0

class Transform
  translation:[0.0, 0.0, 0.0]
  rotation:[0.0, 0.0, 0.0]
  scale:[1.0, 1.0, 1.0]

class Geometry layout primitive vertexBuffer indexBuffer:nil

class Material shader texture:nil uniforms:{}

class Instancing buffer layout

class Drawable geometry material instancing:nil vao:nil

class Node transform:(Transform ()) drawable:nil children:[]

# --- Mutable types ---

class Buffer = {
  def __init__ self ctx data dynamic:false = (
    set! self._buf (ctx.buffer data dynamic:*);
    set! self._sizeBytes nil
  )
  def sizeBytes self =
    if some? self._sizeBytes then self._sizeBytes
    else self._buf.size
  def setSizeBytes self value = set! self._sizeBytes value
  def update self data offset:0 =
    self._buf.write data offset:offset
  def read self = self._buf.read ()
}

def pack data =
  let n = len data in
  let ch = if py.isinstance (first data) int then "i" else "f" in
  struct.pack "<${str n}${ch}" $* data

class Texture = {
  def __init__ self ctx size data:nil = (
    let raw = if some? data then py.bytes data else nil in
    set! self._tex (ctx.texture size 4 data:raw);
    set! self._tex.filter [moderngl.NEAREST, moderngl.NEAREST]
  )
  def update self data = self._tex.write (py.bytes data)
  def read self = self._tex.read ()
}

# --- Shaders ---

def gelpiUbo = """
layout(std140, binding = 0) uniform Gelpi {
    mat4 model;
    mat4 view;
    mat4 projection;
    mat4 mvp;
    vec2 viewport;
    vec3 camera_pos;
    float time;
    vec3 ambient;
    int has_light;
    vec3 light_direction;
    vec3 light_color;
    float light_intensity;
};
"""

def vert = """
#version 430

${gelpiUbo}

in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
in vec4 in_color;

out vec3 v_normal;
out vec3 v_position;
out vec2 v_uv;
out vec4 v_color;

void main() {
    vec4 world_pos = model * vec4(in_position, 1.0);
    v_position = world_pos.xyz;
    v_normal = mat3(model) * in_normal;
    v_uv = in_uv;
    v_color = in_color;
    gl_Position = mvp * vec4(in_position, 1.0);
}
"""

def frag = """
#version 430

${gelpiUbo}

uniform vec4 u_color;
uniform int u_has_vertex_color;
uniform int u_has_texture;
uniform sampler2D u_texture;
uniform int u_lit;

in vec3 v_normal;
in vec3 v_position;
in vec2 v_uv;
in vec4 v_color;

out vec4 fragColor;

void main() {
    vec4 base_color = u_color;

    if (u_has_vertex_color != 0) {
        base_color *= v_color;
    }

    if (u_has_texture != 0) {
        base_color *= texture(u_texture, v_uv);
    }

    if (u_lit != 0) {
        vec3 lighting = ambient;
        if (has_light != 0) {
            vec3 n = normalize(v_normal);
            vec3 l = normalize(-light_direction);
            float diff = max(dot(n, l), 0.0);
            lighting += light_color * light_intensity * diff;
        }
        fragColor = vec4(base_color.rgb * lighting, base_color.a);
    } else {
        fragColor = base_color;
    }
}
"""

def particleVert = """
#version 430

${gelpiUbo}

uniform float u_size;
uniform bool u_screen_space;

in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
in vec3 in_offset;
in vec3 in_color;

out vec3 v_normal;
out vec3 v_position;
out vec2 v_uv;
out vec4 v_color;

void main() {
    v_color = vec4(in_color, 1.0);
    v_normal = in_normal;
    v_uv = in_uv;

    if (u_screen_space) {
        vec4 clip = projection * view * model * vec4(in_offset, 1.0);
        clip.xy += in_position.xy * (2.0 * u_size / viewport) * clip.w;
        gl_Position = clip;
    } else {
        vec3 cam_right = vec3(view[0][0], view[1][0], view[2][0]);
        vec3 cam_up    = vec3(view[0][1], view[1][1], view[2][1]);
        vec3 world_pos = in_offset
                       + cam_right * in_position.x * u_size
                       + cam_up    * in_position.y * u_size;
        gl_Position = projection * view * model * vec4(world_pos, 1.0);
    }
    v_position = gl_Position.xyz;
}
"""

# --- Constructor functions ---

def drawable ctx geom mat instancing:nil =
  Drawable geometry:geom material:mat instancing:*
    vao:(buildVao ctx mat.shader geom instancing:*)

def quadGeometry ctx =
  Geometry
    layout:[["in_position", "3f"], ["in_normal", "3f"], ["in_uv", "2f"]]
    primitive:TRIANGLES
    vertexBuffer:(Buffer ctx [
      -0.5, -0.5, 0.0,   0, 0, 1,   0, 0,
       0.5, -0.5, 0.0,   0, 0, 1,   1, 0,
       0.5,  0.5, 0.0,   0, 0, 1,   1, 1,
      -0.5,  0.5, 0.0,   0, 0, 1,   0, 1
    ])
    indexBuffer:(Buffer ctx [0, 1, 2, 2, 3, 0])

def material ctx color:[1.0, 1.0, 1.0, 1.0] texture:nil lit:true vertexColor:false =
  let prog =
    if py.hasattr ctx "_defaultProg" then ctx._defaultProg
    else
      let p = ctx.program vertex_shader:vert fragment_shader:frag in
      let _ = when contains? p "Gelpi" do set! p.("Gelpi").binding 0 in
      set! ctx._defaultProg p
  in
  let color = if len color == 3 then conj (vec color) 1.0 else color in
  Material shader:prog texture:*
    uniforms:{
      u_color: color,
      u_has_vertex_color: (if vertexColor then 1 else 0),
      u_has_texture: (if some? texture then 1 else 0),
      u_lit: (if lit then 1 else 0),
    }

def particleMaterial ctx color:[1.0, 1.0, 1.0, 1.0] texture:nil vertexColor:true size:1.0 screenSpace:false =
  let prog =
    if py.hasattr ctx "_particleProg" then ctx._particleProg
    else
      let p = ctx.program vertex_shader:particleVert fragment_shader:frag in
      let _ = when contains? p "Gelpi" do set! p.("Gelpi").binding 0 in
      set! ctx._particleProg p
  in
  let color = if len color == 3 then conj (vec color) 1.0 else color in
  Material shader:prog texture:*
    uniforms:{
      u_color: color,
      u_has_vertex_color: (if vertexColor then 1 else 0),
      u_has_texture: (if some? texture then 1 else 0),
      u_lit: 0,
      u_size: size,
      u_screen_space: screenSpace,
    }

# --- Transform math ---

def transformMatrix t =
  let m = glm.mat4 () in
  let m = glm.translate m (glm.vec3 $* t.translation) in
  let m = glm.rotate m t.rotation.(2) (glm.vec3 0 0 1) in
  let m = glm.rotate m t.rotation.(1) (glm.vec3 0 1 0) in
  let m = glm.rotate m t.rotation.(0) (glm.vec3 1 0 0) in
  glm.scale m (glm.vec3 $* t.scale)

def cameraMatrices cam =
  let [yaw, pitch, roll] = cam.orientation in
  let fx = math.sin yaw * math.cos pitch in
  let fy = math.cos yaw * math.cos pitch in
  let fz = math.sin pitch in
  let target = [
    cam.position.(0) + fx,
    cam.position.(1) + fy,
    cam.position.(2) + fz
  ] in
  let rightX = math.cos yaw in
  let rightY = 0.0 - math.sin yaw in
  let up = [
    0.0 - rightX * math.sin roll,
    0.0 - rightY * math.sin roll,
    math.cos roll
  ] in
  let view = glm.lookAt (glm.vec3 $* cam.position) (glm.vec3 $* target) (glm.vec3 $* up) in
  let proj = glm.perspective (math.radians cam.fov) cam.aspect cam.near cam.far in
  [view, proj]

# --- UBO packing (std140 layout, 336 bytes) ---

def uboTail = struct.Struct "<2f2f3ff3fi3ff3ff"

def packUbo model view proj mvp viewport camPos time ambient light =
  let vw = float viewport.(2) in
  let vh = float viewport.(3) in
  let [cx, cy, cz] = camPos in
  let [ax, ay, az] = ambient in
  let [ldx, ldy, ldz, lcx, lcy, lcz, li, hl] =
    if some? light then
      let [ldx, ldy, ldz] = light.direction in
      let [lcx, lcy, lcz] = light.color in
      [ldx, ldy, ldz, lcx, lcy, lcz, light.intensity, 1]
    else [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0]
  in
  let tail = uboTail.pack
    vw vh 0.0 0.0
    cx cy cz time ax ay az hl
    ldx ldy ldz 0.0 lcx lcy lcz li
  in
  model.to_bytes () + view.to_bytes () +
    proj.to_bytes () + mvp.to_bytes () + tail

# --- VAO building ---

def layoutStride layout =
  reduce (fun acc [_, fmt] ->
    acc + int (subs fmt 0 (len fmt - 1)) * 4
  ) 0 layout

def processLayout prog layout =
  let [attrs, fmts] = reduce (fun [attrs, fmts] [attr, fmt] ->
    if contains? prog attr
    then [conj attrs attr, conj fmts fmt]
    else [attrs, conj fmts ("/" + fmt)]
  ) [[], []] layout
  in [attrs, " ".join fmts]

def buildVao ctx prog geom instancing:nil =
  let [attrs, fmtStr] = processLayout prog geom.layout in
  let entry = py.tuple $ concat [geom.vertexBuffer._buf, fmtStr] attrs in
  let content = py.list [entry] in
  let _ = when some? instancing do
    let [instAttrs, instFmtStr] = processLayout prog instancing.layout in
    let instEntry = py.tuple $ concat [instancing.buffer._buf, instFmtStr + "/i"] instAttrs in
    content.append instEntry
  in
  if some? geom.indexBuffer
  then ctx.vertex_array prog content index_buffer:geom.indexBuffer._buf
  else ctx.vertex_array prog content

# --- Render ---

def render ctx camera environment node =
  let vp = environment.viewport in
  let cc = environment.clearColor in
  let _ = set! ctx.viewport vp in
  let _ = ctx.enable moderngl.DEPTH_TEST in
  let _ = if environment.cullFace
    then ctx.enable moderngl.CULL_FACE
    else ctx.disable moderngl.CULL_FACE
  in
  let _ = ctx.clear cc.(0) cc.(1) cc.(2) (if len cc > 3 then cc.(3) else 1.0) in
  let [view, proj] = cameraMatrices camera in
  let ubo =
    if py.hasattr ctx "_ubo" then ctx._ubo
    else set! ctx._ubo (ctx.buffer reserve:336)
  in (
    ubo.bind_to_uniform_block 0;
    walk ctx node (glm.mat4 ()) view proj camera environment ubo
  )

def walk ctx node parentWorld view proj camera env ubo =
  let world = parentWorld * transformMatrix node.transform in (
    when some? node.drawable do
      draw node.drawable world view proj camera env ubo;
    for! child in node.children do
      walk ctx child world view proj camera env ubo
  )

def draw drw world view proj camera env ubo =
  let prog = drw.material.shader in
  let mvp = proj * view * world in
  let uboData = packUbo world view proj mvp env.viewport
    camera.position env.time env.ambient env.light
  in (
    ubo.write uboData;
    for! [name, value] in drw.material.uniforms do
      when contains? prog name do
        set! prog.(name).value value;
    when some? drw.material.texture do (
      drw.material.texture._tex.use 0;
      when contains? prog "u_texture" do
        set! prog.("u_texture").value 0
    );
    if some? drw.instancing then
      let stride = layoutStride drw.instancing.layout in
      let instances = drw.instancing.buffer.sizeBytes () // stride in
      drw.vao.render drw.geometry.primitive instances:instances
    else
      drw.vao.render drw.geometry.primitive
  )
