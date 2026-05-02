package app.marysia.skel.state;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Service-layer logic for the per-user JSON KV store. Mirrors the
 * django-bolt and rust DDD reference services: the storage is private
 * to the user, and the controller never touches the repository
 * directly.
 */
@Service
public class StateService {

    private final ReactStateRepository states;

    public StateService(ReactStateRepository states) {
        this.states = states;
    }

    public Map<String, String> list(long userId) {
        Map<String, String> out = new LinkedHashMap<>();
        for (ReactState s : states.findAllByUserIdOrderByKeyAsc(userId)) {
            out.put(s.getKey(), s.getValue());
        }
        return out;
    }

    public void upsert(long userId, String key, String value) {
        String resolved = value == null ? "" : value;
        ReactState row = states.findByUserIdAndKey(userId, key)
            .orElseGet(() -> new ReactState(userId, key, resolved));
        row.setValue(resolved);
        states.save(row);
    }

    @Transactional
    public void delete(long userId, String key) {
        states.deleteByUserIdAndKey(userId, key);
    }
}
