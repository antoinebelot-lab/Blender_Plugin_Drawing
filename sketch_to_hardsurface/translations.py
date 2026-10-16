# SPDX-License-Identifier: GPL-3.0-or-later
"""French translation of the interface.

Active when Blender's language is French (Preferences > Interface >
Translation, "Interface" ticked). Every message is registered in both the
default and the operator translation contexts, so buttons, tooltips and
reports are all covered. ``tests/test_blender_integration.py`` fails when a
user-visible string has no entry here.
"""

import bpy

FR = {
    # Panels
    "1. References": "1. Références",
    "2. Profiles and Volume": "2. Profils et volume",
    "3. Hard Surface": "3. Hard surface",
    "4. Usable Mesh": "4. Maillage exploitable",
    "Load a sketch, a blueprint or a photo": "Chargez un croquis, un plan ou une photo",
    "Trace the active reference, tune it with F9": "Tracez la référence active, ajustez avec F9",
    "Select cutters, then the target (active)": "Sélectionnez les découpeurs, puis la cible (active)",
    "Export": "Exporter",
    "Axis": "Axe",

    # Roles
    "None": "Aucun",
    "Reference": "Référence",
    "Sketch or inspiration image": "Croquis ou image d'inspiration",
    "Profile": "Profil",
    "2D outline extruded into a solid": "Contour 2D extrudé en volume",
    "Blockout": "Ébauche",
    "Volume built from several profiles": "Volume construit à partir de plusieurs profils",
    "Cutter": "Découpeur",
    "Boolean operand": "Opérande booléen",
    "Final": "Final",
    "Clean, modifier-free mesh ready for export": "Maillage propre, sans modificateur, prêt à exporter",
    "What this object is used for in the sketch to hard surface workflow":
        "Rôle de l'objet dans le processus croquis vers hard surface",

    # Scene
    "Millimetre Scene": "Scène en millimètres",
    "Work in millimetres: metric units, 1 Blender unit = 1 mm, viewport clipping adapted":
        "Travailler en millimètres : unités métriques, 1 unité Blender = 1 mm, découpage de la vue adapté",
    "1 Unit = 1 mm": "1 unité = 1 mm",
    "Set the unit scale to 0.001 so that modifier defaults suit small objects":
        "Échelle d'unité à 0,001 pour que les valeurs par défaut des modificateurs conviennent aux petits objets",
    "Scene set to millimetres": "Scène réglée en millimètres",
    "Show/Hide": "Afficher/masquer",
    "Show or hide every object with this role": "Afficher ou masquer tous les objets ayant ce rôle",
    "Select": "Sélectionner",
    "Select this object and make it active": "Sélectionner cet objet et le rendre actif",
    "Boolean Solver": "Solveur booléen",
    "Solver used by the boolean modifiers this add-on creates":
        "Solveur utilisé par les modificateurs booléens créés par cette extension",

    # References
    "Add Reference": "Ajouter une référence",
    "Load sketches or inspiration images as references aligned to a view, at real-world size":
        "Charger des croquis ou images d'inspiration comme références alignées sur une vue, à taille réelle",
    "View": "Vue",
    "Front": "Avant",
    "Seen from the front view (Numpad 1)": "Vue de face (pavé num. 1)",
    "Back": "Arrière",
    "Seen from the back view (Ctrl Numpad 1)": "Vue arrière (Ctrl pavé num. 1)",
    "Right": "Droite",
    "Seen from the right view (Numpad 3)": "Vue de droite (pavé num. 3)",
    "Left": "Gauche",
    "Seen from the left view (Ctrl Numpad 3)": "Vue de gauche (Ctrl pavé num. 3)",
    "Top": "Dessus",
    "Seen from the top view (Numpad 7)": "Vue de dessus (pavé num. 7)",
    "Bottom": "Dessous",
    "Seen from the bottom view (Ctrl Numpad 7)": "Vue de dessous (Ctrl pavé num. 7)",
    "Inspiration Board": "Planche d'inspiration",
    "Free-floating images arranged on a board, visible in every view":
        "Images libres disposées sur une planche, visibles dans toutes les vues",
    "Real Width": "Largeur réelle",
    "Real-world width covered by the whole image (0: 100 mm, calibrate later)":
        "Largeur réelle couverte par toute l'image (0 : 100 mm, à calibrer ensuite)",
    "Opacity": "Opacité",
    "Depth": "Profondeur",
    "Behind": "Derrière",
    "Always drawn behind the model": "Toujours dessinée derrière le modèle",
    "Default": "Par défaut",
    "Depth tested like any other object": "Profondeur testée comme tout autre objet",
    "In Front": "Devant",
    "Always drawn over the model": "Toujours dessinée par-dessus le modèle",
    "Lock Selection": "Verrouiller la sélection",
    "Make the reference unselectable in the viewport": "Rendre la référence non sélectionnable dans la vue",
    "No image file selected": "Aucun fichier image sélectionné",
    "Only the first image is used for an axis view": "Seule la première image est utilisée pour une vue d'axe",
    "Cannot load %s: %s": "Impossible de charger %s : %s",
    "%d reference(s) added": "%d référence(s) ajoutée(s)",
    "Set Real Width": "Définir la largeur réelle",
    "Resize the active reference so that the whole image has this real width":
        "Redimensionner la référence active pour que l'image entière ait cette largeur réelle",
    "Opacity of All References": "Opacité de toutes les références",
    "Set the opacity of every reference image at once": "Régler en une fois l'opacité de toutes les références",
    "Calibrate Scale": "Calibrer l'échelle",
    "Click two points on the active reference (Shift: horizontal/vertical), then type their real distance":
        "Cliquer deux points sur la référence active (Maj : horizontal/vertical), puis saisir leur distance réelle",
    "Calibrate: click the first point on the reference  (Esc: cancel)":
        "Calibrage : cliquez le premier point sur la référence  (Échap : annuler)",
    "Calibrate: click the second point, Shift: horizontal/vertical  |  %s":
        "Calibrage : cliquez le second point, Maj : horizontal/vertical  |  %s",
    "The two points are identical": "Les deux points sont identiques",
    "Set Real Distance": "Définir la distance réelle",
    "Scale the active reference so that the measured segment gets its real length":
        "Mettre à l'échelle la référence active pour que le segment mesuré ait sa longueur réelle",
    "Real Distance": "Distance réelle",
    "Measured: %s": "Mesuré : %s",
    "Invalid distance": "Distance invalide",
    "Reference scaled by %.4f": "Référence mise à l'échelle × %.4f",

    # Tracing
    "Trace Reference": "Tracer la référence",
    "Vectorise the active reference image into clean profiles (tune it in the Adjust Last Operation panel)":
        "Vectoriser l'image de référence active en profils propres (réglages dans le panneau "
        "Ajuster la dernière opération)",
    "Shape": "Forme",
    "Silhouette": "Silhouette",
    "Outer outline of the drawing, everything inside is filled":
        "Contour extérieur du dessin, tout l'intérieur est rempli",
    "Enclosed Regions": "Zones fermées",
    "One shape per area enclosed by lines (panels, separate parts)":
        "Une forme par zone fermée par des traits (panneaux, pièces séparées)",
    "Inked Areas": "Zones encrées",
    "The inked areas themselves, holes kept (silhouettes, solid fills)":
        "Les zones encrées elles-mêmes, trous conservés (silhouettes, aplats)",
    "Ink": "Encre",
    "Dark on Light": "Foncé sur clair",
    "Pencil or marker on paper": "Crayon ou feutre sur papier",
    "Light on Dark": "Clair sur foncé",
    "Light lines on a dark background": "Traits clairs sur fond foncé",
    "Opaque on Transparent": "Opaque sur transparent",
    "Uses the alpha channel (PNG cut-outs)": "Utilise le canal alpha (PNG détourés)",
    "Threshold": "Seuil",
    "Ink detection level": "Niveau de détection de l'encre",
    "Resolution": "Résolution",
    "Working resolution (longest side, in pixels)": "Résolution de travail (plus grand côté, en pixels)",
    "Close Gaps": "Fermer les trous",
    "Bridge gaps in the lines up to about twice this size":
        "Relier les interruptions de trait jusqu'à environ deux fois cette taille",
    "Remove Thin Parts": "Supprimer les parties fines",
    "Remove parts narrower than about twice this size (construction lines overshooting the corners)":
        "Supprimer les parties plus étroites qu'environ deux fois cette taille (traits de construction "
        "qui dépassent aux coins)",
    "Simplify": "Simplifier",
    "Maximum deviation from the drawing": "Écart maximal par rapport au dessin",
    "Straighten": "Redresser",
    "Snap edges within this angle of horizontal or vertical":
        "Aligner les arêtes proches de l'horizontale ou de la verticale à cet angle près",
    "Ignore Smaller Than": "Ignorer en dessous de",
    "Ignore specks smaller than this part of the image": "Ignorer les taches plus petites que cette part de l'image",
    "Keep Holes": "Garder les trous",
    "Separate Objects": "Objets séparés",
    "One object per shape": "Un objet par forme",
    "Extrude": "Extruder",
    "Give the profile a live thickness": "Donner au profil une épaisseur modifiable",
    "Extrusion depth (0: as wide as the reference)": "Profondeur d'extrusion (0 : largeur de la référence)",
    "Image %s has no pixel data (missing file?)": "L'image %s n'a pas de pixels (fichier manquant ?)",
    "No shape found: adjust Ink, Threshold or Shape": "Aucune forme trouvée : ajustez Encre, Seuil ou Forme",
    "%d shape(s) traced in %.2f s": "%d forme(s) tracée(s) en %.2f s",

    # Profiles
    "Draw Profile": "Dessiner un profil",
    "Start a profile with one vertex at the 3D cursor, then Ctrl+Right-click in an orthographic view to add points":
        "Commencer un profil par un sommet au curseur 3D, puis Ctrl+clic droit dans une vue orthographique "
        "pour ajouter des points",
    "Switch to an orthographic axis view (Numpad 1, 3, 7) to draw flat":
        "Passez dans une vue d'axe orthographique (pavé num. 1, 3, 7) pour dessiner à plat",
    "Ctrl+Right-click to add points, then Extrude Profile":
        "Ctrl+clic droit pour ajouter des points, puis Extruder le profil",
    "Extrude Profile": "Extruder le profil",
    "Close and fill the selected outlines (meshes or curves) and give them a live thickness":
        "Fermer et remplir les contours sélectionnés (maillages ou courbes) et leur donner une épaisseur modifiable",
    "Thickness (0: largest size of the profile)": "Épaisseur (0 : plus grande dimension du profil)",
    "Direction": "Direction",
    "Centered": "Centrée",
    "Extrude on both sides of the drawing plane": "Extruder des deux côtés du plan de dessin",
    "Extrude toward the face normal": "Extruder dans le sens de la normale",
    "Extrude away from the face normal": "Extruder à l'opposé de la normale",
    "Mirror across the YZ plane of the object": "Symétrie par rapport au plan YZ de l'objet",
    "Mirror across the XZ plane of the object": "Symétrie par rapport au plan XZ de l'objet",
    "Mirror across the XY plane of the object": "Symétrie par rapport au plan XY de l'objet",
    "Not a closed flat outline: %s": "Pas un contour plan fermé : %s",
    "Combine Views": "Combiner les vues",
    "Intersect profiles drawn in different views (front, side, top) into one live volume":
        "Intersecter des profils dessinés dans différentes vues (face, côté, dessus) en un volume modifiable",
    "Hide Profiles": "Masquer les profils",
    "The selected profiles are empty": "Les profils sélectionnés sont vides",
    "Blockout built from %d profiles": "Ébauche construite à partir de %d profils",

    # Hard surface
    "Boolean": "Booléen",
    "Use the selected objects as live boolean cutters on the active object":
        "Utiliser les objets sélectionnés comme découpeurs booléens modifiables sur l'objet actif",
    "Operation": "Opération",
    "Cut": "Découper",
    "Subtract the selected objects from the active one": "Soustraire les objets sélectionnés de l'objet actif",
    "Union": "Union",
    "Merge the selected objects into the active one": "Fusionner les objets sélectionnés dans l'objet actif",
    "Intersect": "Intersection",
    "Keep only the volume shared with the selected objects":
        "Ne garder que le volume commun avec les objets sélectionnés",
    "Slice": "Trancher",
    "Cut the active object and keep each cut-out part as a separate live object":
        "Découper l'objet actif et garder chaque partie découpée comme objet séparé modifiable",
    "%d cutter(s) added to %s": "%d découpeur(s) ajouté(s) à %s",
    "Mirror": "Symétrie",
    "Add a live symmetry to the selected objects": "Ajouter une symétrie modifiable aux objets sélectionnés",
    "Bisect": "Couper",
    "Cut away the geometry on the mirrored side": "Supprimer la géométrie du côté symétrisé",
    "Center": "Centre",
    "World Origin": "Origine du monde",
    "Mirror across the world planes": "Symétrie par rapport aux plans du monde",
    "Object Origin": "Origine de l'objet",
    "Mirror across the object's own planes": "Symétrie par rapport aux plans propres de l'objet",
    "Choose at least one axis": "Choisissez au moins un axe",
    "Hard-Surface Finish": "Finition hard surface",
    "Add the hard-surface finishing stack: Smooth by Angle, then an angle-limited bevel with hardened normals":
        "Ajouter la pile de finition hard surface : lissage par angle, puis chanfrein limité par angle "
        "avec normales durcies",
    "Sharp Angle": "Angle vif",
    "Edges sharper than this get crisp shading and a bevel":
        "Les arêtes plus vives que cet angle reçoivent un ombrage net et un chanfrein",
    "Bevel": "Chanfrein",
    "Width": "Largeur",
    "Bevel width (0: 1% of the object size)": "Largeur du chanfrein (0 : 1 % de la taille de l'objet)",
    "Segments": "Segments",
    "0.5 is round, higher is flatter (superellipse)": "0,5 est rond, plus haut est plus plat (superellipse)",
    "Weighted Normals": "Normales pondérées",
    "Add a Weighted Normal modifier (useful for low-poly assets without bevel)":
        "Ajouter un modificateur Normales pondérées (utile pour du low-poly sans chanfrein)",
    "Apply Shape": "Appliquer la forme",
    "Apply mirror, extrusion and booleans into the mesh, keeping the finishing stack live":
        "Appliquer symétrie, extrusion et booléens dans le maillage, en gardant la finition modifiable",
    "Hide Cutters": "Masquer les découpeurs",

    # Usable mesh
    "Check Mesh": "Vérifier le maillage",
    "Check the active object (with its modifiers) for holes, flipped normals and self-intersections":
        "Rechercher trous, normales inversées et auto-intersections sur l'objet actif (avec ses modificateurs)",
    "Size: %s x %s x %s": "Taille : %s x %s x %s",
    "Faces: %d (%d tris, %d quads, %d n-gons)": "Faces : %d (%d triangles, %d quads, %d n-gones)",
    "Volume: %s": "Volume : %s",
    "Open edges (holes): %d": "Arêtes ouvertes (trous) : %d",
    "Edges shared by 3+ faces: %d": "Arêtes partagées par 3 faces ou plus : %d",
    "Inconsistent normals: %d edges": "Normales incohérentes : %d arêtes",
    "Self-intersecting faces: %d": "Faces auto-intersectées : %d",
    "Loose vertices: %d": "Sommets isolés : %d",
    "Zero-area faces: %d": "Faces d'aire nulle : %d",
    "Normals point inward": "Les normales pointent vers l'intérieur",
    "Object scale is not applied": "L'échelle de l'objet n'est pas appliquée",
    "Watertight, ready for 3D printing": "Étanche, prêt pour l'impression 3D",
    "Not watertight: fix the issues above before printing":
        "Non étanche : corrigez les problèmes ci-dessus avant d'imprimer",
    "Problems are selected: Tab to see them in Edit Mode":
        "Problèmes sélectionnés : Tab pour les voir en mode Édition",
    "Make Final Mesh": "Créer le maillage final",
    "Create a clean, modifier-free copy of the selected objects, ready for export or 3D printing":
        "Créer une copie propre et sans modificateur des objets sélectionnés, prête pour l'export "
        "ou l'impression 3D",
    "Clean Up": "Nettoyer",
    "Merge duplicate vertices, remove loose and degenerate geometry, make normals consistent":
        "Fusionner les sommets doublons, supprimer la géométrie isolée ou dégénérée, rendre les normales cohérentes",
    "Merge Distance": "Distance de fusion",
    "0: 0.001 mm": "0 : 0,001 mm",
    "Triangulate": "Trianguler",
    "Apply Scale": "Appliquer l'échelle",
    "Hide Sources": "Masquer les sources",
    "%d final mesh(es), %d watertight": "%d maillage(s) final(aux), %d étanche(s)",
}

translations_dict = {
    "fr_FR": {(ctx, msgid): msgstr for msgid, msgstr in FR.items() for ctx in ("*", "Operator")},
}


def register():
    bpy.app.translations.register(__name__, translations_dict)


def unregister():
    bpy.app.translations.unregister(__name__)
