# tools/frame_load_service.py
from domain.definition import FrameDistributedLoad


class FrameLoadService:
    @staticmethod
    def assign_distributed_load_set(frame_obj, load_set: FrameDistributedLoad):
        """Artık doğrudan güçlendirilmiş FrameDistributedLoad nesnesini set olarak kullanır."""
        if not hasattr(frame_obj, "dist_load_sets"):
            frame_obj.dist_load_sets = {}
        if not hasattr(frame_obj, "dist_loads"):
            frame_obj.dist_loads = []

        pat = load_set.pattern_name
        frame_obj.dist_loads = [dl for dl in frame_obj.dist_loads
                                if dl.pattern_name != pat]

        if load_set.mode == "DELETE":
            frame_obj.dist_load_sets.pop(pat, None)
            frame_obj.mark_dirty()
            return

        frame_obj.dist_load_sets[pat] = load_set
        frame_obj.dist_loads.extend(load_set.to_sap_loads())
        frame_obj.mark_dirty()

    @staticmethod
    def assign_distributed_load(frame_obj, new_load: FrameDistributedLoad):
        """Tekil veya eski API yük atma (geriye dönük uyumluluk)."""
        if not hasattr(frame_obj, "dist_loads"):
            frame_obj.dist_loads = []

        if new_load.mode == "DELETE":
            frame_obj.dist_loads = [
                dl for dl in frame_obj.dist_loads
                if dl.pattern_name != new_load.pattern_name
            ]
            if hasattr(frame_obj, "mark_dirty"):
                frame_obj.mark_dirty()
            return

        existing_idx = next(
            (i for i, dl in enumerate(frame_obj.dist_loads)
             if dl.pattern_name == new_load.pattern_name),
            None
        )

        if existing_idx is not None:
            if new_load.mode == "ADD":
                frame_obj.dist_loads.append(new_load)
            else:
                frame_obj.dist_loads[existing_idx] = new_load
        else:
            frame_obj.dist_loads.append(new_load)

        if hasattr(frame_obj, "mark_dirty"):
            frame_obj.mark_dirty()