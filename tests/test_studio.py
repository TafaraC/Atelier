import base64
import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from atelier.app import Studio
from atelier.store import Store,record,clone,validate
from atelier import narrative
from atelier.geometry import Camera


class Desktop(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.path=Path(self.temp.name)/"studio.sqlite"
        self.store=Store(self.path)
        self.app=Studio(self.store)
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.store.db.close()
        self.temp.cleanup()

    def level(self,dim):
        a=self.app
        with patch("atelier.app.ask",return_value={"Name":"Gate "+dim,"Design type":dim,"Plan convention":"Side-view"}):
            a.new_level()
        a.update()
        return a.active

    def drag(self,tool):
        c=self.app.canvas
        self.app.tool(tool)
        c.press(SimpleNamespace(x=280,y=180))
        c.move(SimpleNamespace(x=360,y=230))
        c.release(SimpleNamespace(x=360,y=230))
        return self.app.selected

    def test_workspace_roundtrip(self):
        a=self.app
        planar=self.level("2D")
        room=self.drag("Room")
        self.assertEqual(a.rows[room]["dimension"],"2D")
        self.drag("Sketch")
        a.undo()
        a.undo(True)
        spatial=self.level("3D")
        for shape in ("Box","Ramp","Cylinder","Plane","Platform"):
            key=self.drag(shape)
            self.assertEqual(len(a.rows[key]["size"]),3)
        a.tool("Route")
        for x,y in ((260,200),(310,230),(350,240)):a.canvas.press(SimpleNamespace(x=x,y=y))
        a.canvas.finish()
        self.assertEqual(len(a.rows[a.selected]["points"]),3)
        with patch("atelier.board.simpledialog.askstring",return_value="Lookout"):
            marker=self.drag("Marker")
        a.change(lambda:a.rows[marker].update(pos=[25,90,30]))
        image=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6WYAAAAASUVORK5CYII=")
        asset=record("asset","Reference",hash=self.store.put(image))
        a.add(asset)
        char=record("character","Wayfarer")
        faction=record("faction","Association")
        lore=record("lore","First charter")
        event=record("event","Founding",date="circa Year 4",refs=[char["id"]])
        graph=record("graph","Alliances")
        timeline=record("timeline","Kingdom")
        for r in (char,faction,lore,event,graph,timeline):a.add(r)
        a.navigate(graph["id"])
        for key in (char["id"],faction["id"]):
            with patch.object(a,"choose",return_value=key):narrative.place_profile(a)
        first,second=narrative.children(a,"node")
        def choose_edge(_,__,fields):
            names=fields[0][2]
            return {"From":names[0],"To":names[1],"Relationship":"Rivalry","Direction":"Mutual"}
        with patch("atelier.narrative.ask",side_effect=choose_edge):narrative.relationship(a)
        a.navigate(timeline["id"])
        with patch("atelier.narrative.simpledialog.askstring",return_value="History"):narrative.add_track(a)
        track=narrative.children(a,"track")[0]
        with patch.object(a,"choose",return_value=event["id"]),patch("atelier.narrative.ask",return_value={
            "Track":"History ["+track["id"][:5]+"]","Start (calendar units)":"4","End (optional)":"9"}):
            narrative.place_event(a)
        a.change(lambda:a.rows[marker].update(refs=[lore["id"]]))
        with TemporaryDirectory() as second_dir:
            second_store=Store(Path(second_dir)/"studio.sqlite")
            imported=second_store.unpack(self.store.pack(a.doc))
            self.assertEqual(imported,a.doc)
            self.assertEqual(second_store.blob(asset["hash"]),image)
            independent=clone(imported)
            validate(independent)
            self.assertFalse(set(independent["records"]) & set(imported["records"]))
            second_store.db.close()
        reopened=Store(self.path)
        self.assertEqual(reopened.projects()[0],a.doc)
        reopened.db.close()
        for key in (planar,spatial,graph["id"],timeline["id"]):
            a.navigate(key)
            self.assertTrue(a.canvas.find_all())

    def test_projection_picking(self):
        cam=Camera()
        for view in ("Top","Front","Side","Orbit"):
            cam.view=view
            for pixel in ((33,42),(-102,56)):
                self.assertTrue(all(abs(x-y)<.00001 for x,y in zip(cam.screen(cam.pick(*pixel,"3D")),pixel)))

    def test_invalid_geometry_and_references(self):
        self.level("3D")
        key=self.drag("Box")
        for changes in (dict(pos=[1,2]),dict(refs=["missing"])):
            invalid=copy.deepcopy(self.app.doc)
            invalid["records"][key].update(changes)
            with self.assertRaises(ValueError):validate(invalid)

