// pick.vert
#version 460 core

layout(location = 0) in vec3 aPos;
layout(location = 3) in uint aPickId;

uniform mat4  mvp;
uniform mat4  model;
uniform float pointSize;

out vec3      v_world_pos;
flat out uint vID;

void main() {
    vec4 world   = model * vec4(aPos, 1.0);
    v_world_pos  = world.xyz;
    gl_Position  = mvp * vec4(aPos, 1.0);
    gl_PointSize = pointSize;
    vID          = aPickId;
}