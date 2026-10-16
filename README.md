# Sketch to Hard Surface — extension Blender

Passer d'un croquis ou d'une image d'inspiration à un modèle 3D **hard surface
exploitable** (rendu, export, impression 3D), sans quitter Blender.

```
 Croquis / photo ──► 1. Références ──► 2. Profils ──► Volume (vues combinées)
                     à taille réelle   tracés ou        │
                                       dessinés         ▼
                         4. Maillage final ◄── 3. Booléens, symétrie,
                         vérifié, exporté      chanfreins (non destructif)
```

Tout reste **non destructif** jusqu'à la fin : les profils, découpeurs et
chanfreins sont des modificateurs ; on corrige un trait du profil, le volume
se met à jour.

- Compatible **Blender 4.2 LTS → 5.2 LTS** (tests automatisés sur les modules `bpy` 4.2.23 et 5.2.2).
- Interface en anglais, **traduite en français** quand Blender est en français.
- Aucun service externe, aucune dépendance à installer (numpy est fourni avec Blender).

## Installation

1. Télécharger `sketch_to_hardsurface-<version>.zip` (artefact de la CI GitHub
   « Tests », ou le construire : `python scripts/build.py` → dossier `dist/`).
2. Blender : *Édition › Préférences › Extensions › ⌄ › Installer depuis le disque…*
3. Le panneau apparaît dans la vue 3D : barre latérale (**N**) › onglet **Sketch2HS**.

## Flux de travail

### 0. Scène en millimètres (recommandé)

**Scène en millimètres** : unités métriques, 1 unité Blender = 1 mm, découpage
de la vue adapté aux petits objets. Les valeurs par défaut des modificateurs
(fusion, symétrie, chanfrein) se comportent alors bien sur des pièces de
quelques centimètres.

### 1. Références

- **Ajouter une référence** : choisir une ou plusieurs images, la **vue**
  (avant, droite, dessus…) et la **largeur réelle** de l'image. L'image est
  placée face à la vue orthographique correspondante (pavé num. 1, 3, 7),
  visible uniquement dans cette vue, derrière le modèle.
- **Planche d'inspiration** : plusieurs images disposées en grille, visibles
  dans toutes les vues (moodboard).
- **Calibrer l'échelle** : cliquer deux points sur un élément dont on connaît
  la cote (Maj = horizontal/vertical), saisir la distance réelle. L'image est
  mise à l'échelle autour du premier point.
- Liste des références : sélection, opacité, verrouillage, visibilité.

### 2. Profils et volume

- **Tracer la référence** : vectorise l'image active en contours propres.
  Tous les réglages se font en direct dans le panneau *Ajuster la dernière
  opération* (**F9**) :

  | Réglage | Effet |
  |---|---|
  | Forme › Silhouette | contour extérieur, intérieur rempli (croquis au trait) |
  | Forme › Zones fermées | une forme par zone entourée de traits (panneaux, pièces) |
  | Forme › Zones encrées | les aplats eux-mêmes, avec leurs trous |
  | Encre | foncé sur clair, clair sur foncé, ou canal alpha (PNG détouré) |
  | Fermer les trous | relie les traits interrompus |
  | Supprimer les parties fines | enlève les traits de construction qui dépassent aux coins |
  | Simplifier | tolérance de simplification (moins de sommets) |
  | Redresser | rend exactement horizontales/verticales les arêtes presque droites |
  | Extruder / Profondeur | épaisseur modifiable (Solidify) ; 0 = largeur de la référence |

- **Dessiner un profil** : crée un sommet au curseur 3D et passe en Édition ;
  ajouter des points avec **Ctrl + clic droit** dans une vue orthographique.
- **Extruder le profil** : ferme et remplit les contours sélectionnés
  (maillages ou courbes, y compris un demi-profil ouvert) et leur donne une
  épaisseur modifiable, avec symétrie optionnelle (dessiner une moitié suffit).
- **Combiner les vues** : sélectionner les profils de face, de côté et/ou de
  dessus → leur **intersection** donne l'ébauche 3D. Elle reste liée aux
  profils : modifier un profil met le volume à jour.

### 3. Hard surface

- **Découper / Union / Intersection / Trancher** : sélectionner les
  découpeurs puis la cible (active). Booléens modifiables ; les découpeurs
  passent en fil de fer, sont rangés dans `S2H Cutters` et parentés à la
  cible. *Trancher* garde la partie découpée comme objet séparé, qui partage
  le maillage de la cible.
- **Symétrie** : modificateur Miroir (origine du monde ou de l'objet), avec coupe.
- **Finition hard surface** : lissage par angle (groupe Geometry Nodes
  fourni) puis chanfrein limité par angle avec normales durcies, épinglés en
  fin de pile — les nouveaux booléens s'insèrent avant automatiquement.
  Option *Normales pondérées* pour le low-poly sans chanfrein.
- **Appliquer la forme** : fige symétrie, extrusion et booléens dans le
  maillage en gardant la finition modifiable.

### 4. Maillage exploitable

- **Vérifier le maillage** : taille, nombre de faces, volume, arêtes
  ouvertes, arêtes non manifold, normales incohérentes ou inversées,
  auto-intersections, sommets isolés, échelle non appliquée. Verdict
  « étanche, prêt pour l'impression 3D ». Sans modificateur, les problèmes
  sont sélectionnés pour être vus en mode Édition.
- **Créer le maillage final** : copie sans modificateur, nettoyée (doublons,
  géométrie dégénérée, normales cohérentes), échelle appliquée,
  triangulation optionnelle, rangée dans `S2H Final`. Les sources sont
  masquées, pas supprimées.
- Export **STL** / **OBJ** de la sélection.

## Conseils pour les croquis

- Scanner ou photographier bien à plat, avec un bon contraste ; recadrer sur
  la vue utile.
- Une vue par image (face, côté, dessus), à la même échelle si possible ; la
  calibration corrige les écarts.
- Pour la silhouette, le contour extérieur doit être **fermé** (sinon
  augmenter *Fermer les trous*).
- Les ombrages, hachures et annotations à l'intérieur de la silhouette ne
  gênent pas en mode *Silhouette*. En revanche, les cotes et textes à
  l'extérieur deviennent des formes supplémentaires : les effacer de l'image,
  augmenter *Ignorer en dessous de*, ou supprimer ces formes en mode Édition.

## Développement

```
sketch_to_hardsurface/      extension (dossier installé dans Blender)
  blender_manifest.toml     manifeste d'extension (Blender 4.2+)
  core/image_trace.py       vectorisation : numpy pur, sans bpy
  operators/                références, tracé, profils, booléens, export
  ui/panels.py              panneau latéral
  translations.py           traduction française
tests/
  test_image_trace.py       tests du cœur (numpy seul)
  test_blender_integration.py  tests de bout en bout dans Blender (module bpy)
scripts/build.py            construction du zip d'extension
```

Tests :

```bash
pip install numpy pytest            # cœur seul
pip install bpy==5.2.2              # + tests Blender (Python 3.13)
pytest tests
```

Le module `bpy` 4.2 (Python 3.11) permet de vérifier la version minimale.
Un test échoue si une chaîne d'interface n'a pas de traduction française.

## Limites connues

- Le tracé fonctionne sur des images contrastées (croquis au trait,
  silhouettes, plans). Une photo d'objet réel demande d'abord un détourage ;
  elle reste utilisable comme référence ou planche d'inspiration.
- Les traits de construction qui croisent l'intérieur d'une zone en mode
  *Zones fermées* restent visibles sous forme d'encoches.
- La combinaison de vues donne l'enveloppe commune aux silhouettes (pas les
  creux invisibles de face, de côté et de dessus) : on les ajoute ensuite par
  booléens.
- Les outils interactifs (calibration, dessin de profil) et l'affichage
  effectif de la traduction ne sont pas couverts par les tests automatisés.

## Pistes

- Conversion directe des dessins Grease Pencil en profils.
- Lignes de panneaux (rainures) à partir des *Zones fermées*.
- Génération 3D assistée par IA à partir d'une image (service externe, en option).

## Licence

GPL-3.0-or-later (obligatoire pour les extensions Blender), voir `LICENSE`.
