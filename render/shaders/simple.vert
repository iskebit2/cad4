#version 460 core

layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aColor;
layout(location = 2) in vec3 aColorBuffer;
layout(location = 3) in uint aObjectID;
layout(location = 4) in vec3 aCenter;

out vec3 VertexColor;
flat out uint ObjectID;

uniform mat4 mvp;

void main()
{
    gl_Position = mvp * vec4(aPos, 1.0);

    // Gerçek render rengini kullan
    VertexColor = aColorBuffer;

    ObjectID = aObjectID;

    gl_PointSize = 6.0;
}