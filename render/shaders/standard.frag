#version 460 core

in vec3 FragPos;
in vec3 Normal;
in vec3 VertexColor;
flat in uint vID;

layout(location = 0) out vec4 FragColor;
layout(location = 1) out uint FragID;

const vec3 SELECTION_COLOR = vec3(1.0, 0.5, 0.0);

uniform bool  useVertexColor;
uniform vec3  objectColor;
uniform float alpha;
uniform int   renderMode;

#define MAX_LIGHTS 8

layout(std140, binding = 0) uniform LightData {
    int   lightCount;
    float pad1, pad2, pad3;

    vec4  lightPositions[MAX_LIGHTS];
    vec4  lightColors[MAX_LIGHTS];

    vec4  viewPos;

    float ambientStrength;
    float diffuseStrength;
    float specularStrength;
    float shininess;
    float globalBrightness;
} lights;

uniform float rimPower;
uniform float rimIntensity;


// ------------------------------------------------------------
// SEÇİM
// ------------------------------------------------------------

bool is_selected_color(vec3 c)
{
    return abs(c.r - 1.0) < 0.05 &&
           abs(c.g - 0.5) < 0.05 &&
           abs(c.b)       < 0.05;
}


// ------------------------------------------------------------
// MAIN
// ------------------------------------------------------------

void main()
{
    vec3 norm = normalize(Normal);

    bool selected = is_selected_color(VertexColor);

    vec3 baseColor;
    vec3 finalColor;

    if (selected)
    {
        baseColor = SELECTION_COLOR;
    }
    else if (renderMode == 0)
    {
        // Normal debug
        baseColor = norm * 0.5 + 0.5;
    }
    else
    {
        baseColor = useVertexColor
                  ? VertexColor
                  : objectColor;
    }


    // --------------------------------------------------------
    // NORMAL / DEBUG MODE
    // --------------------------------------------------------

    if (renderMode == 0)
    {
        FragColor = vec4(baseColor, alpha);
        FragID    = vID;
        return;
    }


    // --------------------------------------------------------
    // SHADED
    // --------------------------------------------------------

    vec3 totalLighting =
        baseColor * lights.ambientStrength;


    int numLights = clamp(
        lights.lightCount,
        0,
        MAX_LIGHTS
    );


    for (int i = 0; i < numLights; i++)
    {
        vec3 lightDir =
            normalize(lights.lightPositions[i].xyz);

        vec3 lightColor =
            lights.lightColors[i].xyz;


        // ----------------------------------------------------
        // DIFFUSE
        // ----------------------------------------------------

        float NdotL =
            max(dot(norm, lightDir), 0.0);

        totalLighting +=
            baseColor *
            lightColor *
            NdotL *
            lights.diffuseStrength;


        // ----------------------------------------------------
        // SPECULAR
        // ----------------------------------------------------

        if (lights.specularStrength > 0.0 &&
            NdotL > 0.0)
        {
            vec3 viewDir =
                normalize(
                    lights.viewPos.xyz - FragPos
                );

            vec3 halfwayDir =
                normalize(
                    lightDir + viewDir
                );

            float NdotH =
                max(dot(norm, halfwayDir), 0.0);

            float spec =
                pow(
                    NdotH,
                    max(lights.shininess, 1.0)
                );

            totalLighting +=
                lightColor *
                spec *
                lights.specularStrength;
        }
    }


    // --------------------------------------------------------
    // VERY SOFT RIM
    // --------------------------------------------------------

    if (rimIntensity > 0.0)
    {
        vec3 viewDir =
            normalize(
                lights.viewPos.xyz - FragPos
            );

        float NdotV =
            max(dot(norm, viewDir), 0.0);

        float fresnel =
            pow(
                1.0 - NdotV,
                max(rimPower, 1.0)
            );

        totalLighting +=
            baseColor *
            fresnel *
            rimIntensity;
    }


    // --------------------------------------------------------
    // BRIGHTNESS
    // --------------------------------------------------------

    finalColor = totalLighting *
                 lights.globalBrightness;


    // --------------------------------------------------------
    // SOFT TONEMAP
    // --------------------------------------------------------

    finalColor =
        finalColor /
        (finalColor + vec3(1.0));


    // --------------------------------------------------------
    // GAMMA
    // --------------------------------------------------------

    finalColor =
        pow(
            max(finalColor, vec3(0.0)),
            vec3(1.0 / 2.2)
        );


    FragColor = vec4(finalColor, alpha);
    FragID    = vID;
}